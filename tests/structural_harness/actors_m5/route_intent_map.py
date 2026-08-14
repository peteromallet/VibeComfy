"""M5 route-intent map evidence builder.

Runs the canonical four-route taxonomy deterministically through the executor
with fake classifications and freezes the resulting executor envelopes so the
rubric can verify route → phase gates → Apply eligibility.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest import mock

from tests.structural_harness.actors import _write_command_log_jsonl
from vibecomfy.executor.agent_research_stage import AgentResearchTrace
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ImplementationResult,
)
from vibecomfy.executor.core import run_executor
from vibecomfy.executor.evidence_pack import EvidencePack


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
    *_args: Any,
    plan: ClassifyDecision | None = None,
    **_kwargs: Any,
) -> str:
    return f"reply for {plan.route if plan else 'unknown'}"


def _fake_handle_agent_edit(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return {
        "graph": payload.get("graph"),
        "message": "Edited graph.",
    }


def _fake_agent_research(
    *,
    route: str,
    question: str,
    spec: Any | None = None,
    **_kwargs: Any,
) -> tuple[AgentResearchTrace, EvidencePack]:
    """Stub the ACTIVE C1 research seam with a minimal inert trace + pack."""
    return (
        AgentResearchTrace(
            route=route,
            question=question,
            iterations=(),
            final_verdict="enough",
            summary="Synthetic route-intent research.",
            citations=(),
            uncertainty="",
            status="ok",
            elapsed_seconds=0.0,
        ),
        EvidencePack(),
    )


def _fake_implementation(
    request: ExecutorRequest,
    *_args: Any,
    **_kwargs: Any,
) -> ImplementationResult:
    return ImplementationResult(message="Edited graph.", graph=request.graph)


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
            mock.patch("vibecomfy.executor.core.run_agent_research_stage", side_effect=_fake_agent_research),
            mock.patch("vibecomfy.executor.core._run_implement", side_effect=_fake_implementation),
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
        + "\n"
        + json.dumps({"op": "finalize_metadata", "status": "completed"})
        + "\n",
        encoding="utf-8",
    )

    ts = time.time()
    _write_command_log_jsonl(
        root / "command_log.jsonl",
        [
            {
                "ts": ts + index * 0.1,
                "command": "executor",
                "argv": ["executor", "route-intent", record["expected_route"]],
                "exit_code": 0,
                "summary": (
                    "Synthetic: executor produced "
                    f"{record['result_route']} with apply_eligible={record['apply_eligible']}"
                ),
            }
            for index, record in enumerate(records)
        ],
    )

    (root / "report.md").write_text(
        "Deterministic route-intent map for clarify/inspect/revise/adapt.\n",
        encoding="utf-8",
    )

    return {
        "scenario": "route-intent-map",
        "route_map_path": str(route_map_path),
        "actions_path": str(actions_path),
        "command_log_path": str(root / "command_log.jsonl"),
        "report_path": str(root / "report.md"),
    }
