"""B03 — two-step execute prompt goldens + STAGES sequence + tool exactness.

Proves every authoritative design section is present, the visible stage
sequence is ``research → change → submit``, the catalog rendered is exactly the
route-allowed set (no union-catalog leakage), and the golden fixtures match the
builder byte-for-byte.
"""

from __future__ import annotations

from pathlib import Path

from vibecomfy.executor.prompts import (
    _extract_json_object,
    build_two_step_execute_messages,
)
from vibecomfy.executor.agent_backend import _parse_host_action
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
                # ``_build`` uses plan=None (one-step), so the ROUTE/INPUT
                # section is the query-only variant.
                "ROUTE / QUERY (one-step: no classifier plan)",
                "CURRENT WORKFLOW (render lenses)",
                "RESEARCH",
                "PRECEDENT TRANSLATION",
                "EDITING",
                "REPLY",
                "PRIOR TURNS (this window)",
                "CURRENT MESSAGE",
            ):
                assert section in user, (route, section)


GROUNDING_SENTENCE = (
    "Never assert a causal mechanism for a widget/setting unless you can cite "
    "the schema or documentation that states it; if unsure, describe the "
    "observed value and mark the mechanism as unverified.  When no schema or "
    "fetched-doc evidence is available for a setting, state \"unknown\" and "
    "give NO numeric recommendations."
)


class TestGroundingInstruction:
    def test_grounding_present_in_research_and_reply(self) -> None:
        """RC6: the execute prompt constrains causal widget-semantics claims in
        both the RESEARCH and REPLY sections."""
        for route in ROUTES:
            user = _build(route)[1]["content"]
            assert GROUNDING_SENTENCE in user, route
            # Present in BOTH the RESEARCH and REPLY sections.
            research = user.split("RESEARCH")[1].split("PRECEDENT TRANSLATION")[0]
            reply = user.split("REPLY")[1].split("PRIOR TURNS")[0]
            assert GROUNDING_SENTENCE in research, route
            assert GROUNDING_SENTENCE in reply, route


class TestKnownGraphContextFallback:
    def test_known_graph_context_renders_in_research_section(self) -> None:
        """RC4: the graph census is injected into the RESEARCH section so a
        research route that exhausts its search budget can still answer from
        known graph context."""
        messages = build_two_step_execute_messages(
            FIXED_QUERY,
            route="research",
            graph_render=FIXED_GRAPH_RENDER,
            known_graph_context="node 7: KSampler (steps=20)",
        )
        user = messages[1]["content"]
        assert "Known graph context" in user
        assert "node 7: KSampler (steps=20)" in user
        # It lands in the RESEARCH section (before PRECEDENT TRANSLATION).
        research = user.split("RESEARCH")[1].split("PRECEDENT TRANSLATION")[0]
        assert "node 7: KSampler (steps=20)" in research

    def test_absent_known_graph_context_omits_the_block(self) -> None:
        user = _build("research")[1]["content"]
        assert "Known graph context" not in user


class TestHostActionParseFirstWins:
    """P0 PARSE-MULTI-JSON: the parser is balanced and FIRST-WINS.

    A ``{tool_call}{submit}`` concatenation must yield only the tool_call; the
    trailing submit is quarantined, never silently executed.
    """

    def test_tool_call_plus_submit_yields_tool_call(self) -> None:
        action = _parse_host_action(
            '{"action": "tool_call", "tool": "node_schema", "args": {"node_class": "KSampler"}}'
            '{"action": "submit", "reply": "done"}'
        )
        assert action["action"] == "tool_call"
        assert action["tool"] == "node_schema"

    def test_edit_tool_call_plus_submit_yields_tool_call(self) -> None:
        action = _parse_host_action(
            '{"action": "tool_call", "tool": "edit_node", '
            '"args": {"target": "rodin3d_regular", "field": "mesh_detail", "value": "1M-Triangle"}}'
            '{"action": "submit", "reply": "done"}'
        )
        assert action["action"] == "tool_call"
        assert action["tool"] == "edit_node"

    def test_fenced_json_object(self) -> None:
        parsed = _extract_json_object(
            '```json\n{"action": "tool_call", "tool": "edit_node", "args": {"target": "n"}}\n```'
        )
        assert parsed["action"] == "tool_call"

    def test_braces_inside_strings_are_balanced(self) -> None:
        # The greedy ``\\{.*\\}`` regex used to span braces inside strings; the
        # balanced raw_decode scan must not.
        parsed = _extract_json_object(
            '{"action": "edit_node", "args": {"value": "{not json} and {more}"}}'
            '{"action": "submit", "reply": "done"}'
        )
        assert parsed["action"] == "edit_node"
        assert "{not json} and {more}" in parsed["args"]["value"]

    def test_trailing_prose_is_ignored(self) -> None:
        parsed = _extract_json_object(
            '{"action": "tool_call", "tool": "edit_node", "args": {}} trailing prose after the object'
        )
        assert parsed["action"] == "tool_call"

    def test_no_json_object_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            _extract_json_object("no json here at all")

    def test_unknown_action_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            _parse_host_action('{"action": "dance", "steps": 3}')


class TestEditDeliveryRefusalPrompt:
    """P1: the prompt instructs graph-checked refusal and exact bindings."""

    def test_edit_delivery_section_present(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert "EDIT DELIVERY AND REFUSAL" in system, route

    def test_check_graph_before_claiming_absence(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert "inspect the" in system and "CURRENT WORKFLOW render" in system, route
            assert "registered and may be reused or re-instantiated" in system, route

    def test_copy_exact_rendered_binding(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert "Use the EXACT rendered" in system, route

    def test_refusal_only_after_proven_absence(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert (
                "Emit the `requires_custom_nodes` refusal ONLY after a named class"
                in system
            ), route
            assert "proven absent by a failed `node_schema` lookup" in system, route


class TestSingleObjectPerMessagePrompt:
    """P0 prompt strengthening: one object per continuation, wait for feedback."""

    def test_never_emit_two_objects_instruction(self) -> None:
        for route in ROUTES:
            system = _build(route)[0]["content"]
            assert "Return EXACTLY ONE object per message" in system, route
            assert "Never emit two objects back-to-back" in system, route
            assert "after a tool call, STOP and wait for host" in system, route
