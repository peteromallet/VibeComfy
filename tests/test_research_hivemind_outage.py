"""Regression coverage for typed Hivemind statement-timeout outages."""

from __future__ import annotations

from typing import Any, Mapping

from vibecomfy.executor import agent_research_stage as stage
from vibecomfy.executor.tool_contracts import ToolDiagnostic, ToolResult, ToolStatus


_QUESTION = "Which node class provides the requested conditioning path?"


def _statement_timeout_unavailable() -> ToolResult:
    return ToolResult(
        tool_name="hivemind_search",
        status=ToolStatus.UNAVAILABLE,
        diagnostics=(
            ToolDiagnostic(
                code="hivemind_statement_timeout",
                message=(
                    "Hivemind statement timeout after persistent Postgres 57014"
                ),
            ),
        ),
    )


class TestResearchHivemindOutage:
    def test_outage_is_recorded_as_unavailable_not_empty_corpus(self) -> None:
        seen_digests: list[str] = []

        def judge(
            _question: str,
            evidence_digest: str,
            messages: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            seen_digests.append(evidence_digest)
            if len(seen_digests) == 1:
                return {
                    "action": "call",
                    "tool": "hivemind_search",
                    "args": {"query": "conditioning class"},
                }
            return {
                "action": "finish",
                "conclusion": (
                    "Hivemind is unavailable after a statement timeout, so corpus "
                    "coverage remains unknown; implementation must use node_schema "
                    "to check the local inventory."
                ),
                "evidence_ids": [],
                "uncertainty": "No corpus evidence was available during the outage.",
            }

        trace, pack = stage.run_agent_research_stage(
            route="adapt",
            question=_QUESTION,
            judge_fn=judge,
            tool_fn=lambda _tool, _args: _statement_timeout_unavailable(),
            max_turns=3,
        )

        assert trace.status == "ok"
        assert trace.executed_tool_calls == 1
        assert len(seen_digests) == 2
        outage_digest = seen_digests[-1].casefold()
        assert "hivemind_search → unavailable" in outage_digest
        assert "statement timeout" in outage_digest
        assert "no_results" not in outage_digest

        search_entries = [
            entry
            for entry in pack.ledger.entries
            if entry.decision == stage.DECISION_SEARCH
        ]
        assert len(search_entries) == 1
        assert search_entries[0].tool_status == ToolStatus.UNAVAILABLE.value
        assert "statement timeout" in search_entries[0].conclusion.casefold()

        ledger_text = "\n".join(
            f"{entry.tool_status} {entry.conclusion} {entry.uncertainty}"
            for entry in pack.ledger.entries
        ).casefold()
        assert "no_results" not in ledger_text
        assert "corpus lacks" not in ledger_text
        assert "not in corpus" not in ledger_text

    def test_three_statement_timeout_unavailable_results_open_circuit(self) -> None:
        executed_calls = 0

        def always_search(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "action": "call",
                "tool": "hivemind_search",
                "args": {"query": "same slow query"},
            }

        def unavailable_tool(
            _tool: str,
            _args: Mapping[str, Any],
        ) -> ToolResult:
            nonlocal executed_calls
            executed_calls += 1
            return _statement_timeout_unavailable()

        trace, pack = stage.run_agent_research_stage(
            route="adapt",
            question=_QUESTION,
            judge_fn=always_search,
            tool_fn=unavailable_tool,
        )

        assert executed_calls == stage.HIVEMIND_TIMEOUT_CIRCUIT_THRESHOLD == 3
        assert trace.status == "exhausted"
        assert trace.attempt == stage.RESEARCH_ATTEMPT_EMPTY
        assert trace.executed_tool_calls == 3
        assert trace.evidence_artifact_count == 0
        assert any(
            entry.decision == stage.DECISION_HIVEMIND_CIRCUIT_OPEN
            for entry in pack.ledger.entries
        )
        assert "reason=hivemind_timeout_circuit" in " ".join(trace.warnings)

    def test_enough_check_prompt_names_outage_and_local_inventory_handoff(self) -> None:
        messages = stage.build_agent_research_messages(
            question=_QUESTION,
            evidence_digest=(
                "- hivemind_search → unavailable\n"
                "    Hivemind statement timeout after persistent Postgres 57014"
            ),
            route="adapt",
        )

        system = messages[0]["content"]
        assert "Hivemind `unavailable`" in system
        assert "`hivemind_statement_timeout`" in system
        assert "not proof" in system
        assert "`node_schema(node_class)`" in system
        assert "local inventory" in system
