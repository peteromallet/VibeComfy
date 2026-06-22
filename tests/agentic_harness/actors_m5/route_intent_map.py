"""M5 route-intent map evidence builder.

Runs the canonical four-route taxonomy deterministically through the executor
with fake classifications and freezes the resulting executor envelopes so the
rubric can verify route → phase gates → Apply eligibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest import mock

from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
from vibecomfy.executor.core import run_executor


def _fake_classify_for_route(expected_route: str, intent: str, task: str) -> Any:
    """Return a fake classify side effect for the given canonical route."""
    def _classify(
        query: str,
        *,
        route: str = "",
        model: str = "",
        has_graph: bool = False,
        graph_summary: str | None = None,
        **kwargs: Any,
    ) -> ClassifyDecision:
        return ClassifyDecision(
            research=expected_route == "adapt",
            implement=expected_route in {"revise", "adapt"},
            reply=True,
            effort="low" if expected_route in {"clarify", "revise"} else "medium",
            plan_summary=f"{expected_route} plan",
            intent=intent,
            route=expected_route,
            task=task,
        )
    return _classify


def _fake_reply(
    query: str,
    *,
    route: str = "",
    model: str = "",
    plan: ClassifyDecision | None = None,
    **kwargs: Any,
) -> str:
    return f"reply for {plan.route if plan else 'unknown'}"


def _fake_handle_agent_edit(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return {
        "graph": payload.get("graph"),
        "message": "Edited graph.",
    }


def build_m5_route_intent_map_evidence(report_dir: Path) -> dict[str, Any]:
    """Freeze executor envelopes for all four canonical routes."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    cases = [
        ("clarify", "respond", "respond", "make it more cinematic"),
        ("inspect", "explain_graph", "inspect_graph", "what does this workflow do?"),
        ("revise", "edit", "edit_graph", "change the seed to 42"),
        ("adapt", "edit", "research_precedent", "add the Wan control LoRA chain"),
    ]

    records: list[dict[str, Any]] = []
    for route, intent, task, query in cases:
        classify_fn = _fake_classify_for_route(route, intent, task)
        request = ExecutorRequest(
            query=query,
            graph={"nodes": [{"id": 1, "class_type": "KSampler"}]},
            profile="default",
        )
        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=classify_fn),
            mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=_fake_reply),
            mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=_fake_handle_agent_edit),
            mock.patch("vibecomfy.executor.research.build_search_corpus", return_value=[]),
        ):
            result = run_executor(request)

        records.append({
            "expected_route": route,
            "query": query,
            "result_route": result.turn.route,
            "research": result.report.plan.research,
            "implement": result.report.plan.implement,
            "apply_eligible": result.turn.apply_eligible,
            "no_candidate_reason": result.turn.no_candidate_reason,
            "ok": result.ok,
        })

    route_map_path = root / "route_intent_map.json"
    route_map_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    actions_path = root / "actions.jsonl"
    actions_path.write_text(
        "\n".join(
            json.dumps({
                "op": "route_intent_map",
                "route": r["expected_route"],
                "result_route": r["result_route"],
                "apply_eligible": r["apply_eligible"],
            })
            for r in records
        )
        + "\n",
        encoding="utf-8",
    )

    (root / "report.md").write_text(
        "Deterministic route-intent map for clarify/inspect/revise/adapt.\n",
        encoding="utf-8",
    )

    return {
        "scenario": "route-intent-map",
        "route_map_path": str(route_map_path),
        "actions_path": str(actions_path),
        "report_path": str(root / "report.md"),
    }
