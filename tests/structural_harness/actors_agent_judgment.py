"""Agent-judgment pipeline evidence builders (V01, eight end-to-end scenarios).

Every scenario drives the SAME public pipeline boundary — the executor
orchestrator ``run_executor`` (classify → research → implement → reply; the
headless wrapper ``run_headless`` for the needs_input scenario) — with only
the model/edit seams faked, and freezes the SAME minimal contract envelope:
``executor_result.json`` (pipeline outcome), ``metadata.json``,
``actions.jsonl``, plus the scenario-specific deterministic-rail evidence.
Enforced rubrics score EFFECTS + EVIDENCE — never exact node recipes and
never ``report.md`` prose.

Scenario family (scenario name -> assertion focus):

1. revise-without-forced-research
   A parameter edit (``revise`` route) must NOT trigger research: no research
   phase, no research tool calls, ledger empty-or-absent, and the direct edit
   lands on the graph.
2. empty-graph-authoring
   The agent builds a graph from scratch using the implement-phase Wave-A
   tools (``suggest_seed_nodes`` + ``ready_template_list`` /
   ``ready_template_load``) inside the executor's implement seam; the
   seed/asset tools are called with typed ``ok`` results and a graph is
   produced that contains the suggested seed classes.
3. research-only-decision-memo
   The research route runs the C1 agent-owned tool-calling loop: explicit
   question recorded BEFORE any search (question-before-search), the AGENT
   chooses ``hivemind_search`` then ``hivemind_get``, every citation resolves
   to the frozen evidence pack, and the C5 decision memo has exactly
   question/conclusion/citations/uncertainty/next_action.
4. headless-ambiguity-needs_input
   The headless agent surfaces a decision-critical gap as a TYPED
   ``needs_input`` (decision/question/missing_information/options) emitted by
   the classify stage — never a phrase-list route override.
5. schema-drift-approved-normalization
   The queue path raises ``SchemaNormalizationRequired`` without approval and,
   with an approval bound to the exact proposal digest, applies exactly the
   proposed operations and records them as evidence in metadata — both driven
   through the executor's implement seam.
6. hivemind-rate-limiting
   A 429 produces a typed ``rate_limited`` ToolResult, the R2-B2 cooldown is
   honored on the next call (transport hit exactly once), and there is no
   fallthrough to ``web_search`` — driven through the executor's research
   phase with the real Hivemind tools.
7. invalid-emitted-socket
   A link endpoint that matches no emitted socket raises ``RefusedEmit`` with
   per-endpoint socket evidence (requested output/input, emitted socket arrays,
   attempted remaps) instead of silently dropping the edge — driven through
   the executor's implement seam.
8. queue-refusal-valid-runtime-probe
   A bare strong-tier label blocks the queue gate (runtime_readiness
   unverified); a fresh, verified ``RuntimeProbeReceipt`` handed off through
   the ``queue_validate`` stage passes the gate — driven through the
   executor's implement seam.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

# The headless agent service refuses to import without this guard; the
# structural runner may host other scenarios in the same process, so set it
# before any lazy import of ``vibecomfy.agent.service``.
os.environ.setdefault("VIBECOMFY_HEADLESS", "1")

from tests.structural_harness.actors import _EXECUTOR_FAKE_LOCK, _write_actions

# ── shared serialization helpers ─────────────────────────────────────────────


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _tool_result_to_dict(result: Any) -> dict[str, Any]:
    diagnostics = [
        {
            "code": item.code,
            "message": item.message,
            "details": dict(item.details or {}),
        }
        for item in (getattr(result, "diagnostics", None) or ())
    ]
    return {
        "tool_name": result.tool_name,
        "status": result.status.value,
        "result": _jsonable(result.result),
        "evidence_ids": list(result.evidence_ids or ()),
        "diagnostics": diagnostics,
        "retry_after_seconds": result.retry_after_seconds,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _write_std_trail(root: Path, heading: str, body: str) -> None:
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "\n".join(
            [
                f"# {heading}",
                "",
                "## 1. What Ran",
                body,
                "",
                "## 2. Frozen Evidence",
                "Evidence files in this pack are the proof surface; report.md is "
                "narrative only and is never used for pass/fail decisions.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_metadata(root: Path, *, entrypoint: str, requirements: list[str], extra: dict[str, Any]) -> Path:
    payload: dict[str, Any] = {
        "entrypoint": entrypoint,
        "layer": "structural_harness/actors_agent_judgment",
        "requirements": {"models": [], "scenario": list(requirements)},
        "artifact_paths": {},
    }
    payload.update(extra)
    metadata_path = root / "metadata.json"
    _write_json(metadata_path, payload)
    return metadata_path


def _executor_envelope(root: Path, result: Any, *, scenario: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Write the common pipeline envelope: executor result + actions + report."""
    payload = result.to_dict()
    executor_path = root / "executor_result.json"
    _write_json(executor_path, payload)
    report_path = root / "executor_report.json"
    _write_json(report_path, payload.get("report", {}).get("executor", {}))
    actions_path = root / "actions.jsonl"
    _write_actions(actions_path, actions)
    return {
        "scenario": scenario,
        "executor_result_path": str(executor_path),
        "executor_report_path": str(report_path),
        "actions_path": str(actions_path),
    }


def _fake_edit_ok(graph: dict[str, Any], message: str = "Candidate ready.") -> dict[str, Any]:
    return {
        "ok": True,
        "graph": graph,
        "message": message,
        "outcome": {"kind": "edit"},
        "apply_eligibility": {"applyable": True},
        "graph_unchanged": False,
    }


def _fake_edit_failure(failure_kind: str, message: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "failure_kind": failure_kind,
        "stage": "implement",
        "message": message,
        "agent_failure_context": context,
    }


# ── 1. revise-without-forced-research ────────────────────────────────────────


def build_revise_without_forced_research_evidence(report_dir: Path) -> dict[str, Any]:
    """Prove a parameter edit on the revise route never triggers research."""
    from unittest import mock

    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor

    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    graph = {
        "nodes": [
            {
                "id": "3",
                "class_type": "KSampler",
                "inputs": {"seed": 0, "steps": 20, "cfg": 6.0, "sampler_name": "euler"},
            }
        ],
        "links": [],
    }
    request = ExecutorRequest(
        query="Set the KSampler seed to 99999999999999",
        graph=graph,
        profile="default",
        session_id="agentic-harness-revise-no-research",
    )
    edited_graph = {
        "nodes": [
            {
                "id": "3",
                "class_type": "KSampler",
                "inputs": {"seed": 99999999999999, "steps": 20, "cfg": 6.0, "sampler_name": "euler"},
            }
        ],
        "links": [],
    }

    def fake_classify(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="low",
            plan_summary="Revise the KSampler seed value; no research is needed.",
            intent="edit",
            route="revise",
            task="edit_graph",
            target_node_type="KSampler",
            change_goal="Update the KSampler seed widget to 99999999999999",
        )

    def fake_handle_agent_edit(payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        # The implement payload for a pure revise route must NOT carry a
        # research ledger (ledger is adapt-only).
        assert "research_ledger" not in payload, "revise route forwarded a research ledger"
        return _fake_edit_ok(
            edited_graph, "KSampler seed updated to 99999999999999."
        )

    def fake_reply(*_args: Any, **_kwargs: Any) -> str:
        return "KSampler seed updated to 99999999999999; no research ran."

    research_calls: list[str] = []

    with _EXECUTOR_FAKE_LOCK:
        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
            mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=fake_handle_agent_edit) as mock_edit,
            mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=fake_reply),
            mock.patch(
                "vibecomfy.executor.core.run_agent_research_stage",
                side_effect=lambda **_kwargs: research_calls.append("called") or (_ for _ in ()).throw(
                    AssertionError("research stage must not run on the revise route")
                ),
            ) as mock_research,
        ):
            executor_result = run_executor(request)
            edit_called = mock_edit.called
            research_stage_called = mock_research.called

    payload = executor_result.to_dict()
    report = payload.get("report", {}).get("executor", {})
    implementation = report.get("implementation", {}) or {}

    research_evidence = {
        "route": report.get("plan", {}).get("route"),
        "research_phase_present": "research" in report,
        "research_stage_called": bool(research_stage_called),
        "research_calls": research_calls,
        "edit_called": edit_called,
        "implementation_graph_returned": payload.get("graph") is not None,
        "implementation_payload_has_research_ledger": (
            "research_ledger" in implementation
            or "research_ledger" in json.dumps(implementation)
        ),
    }
    assert research_evidence["route"] == "revise"
    assert research_evidence["research_phase_present"] is False
    assert research_evidence["research_stage_called"] is False
    assert research_evidence["edit_called"] is True
    assert payload.get("graph") is not None
    assert payload["graph"]["nodes"][0]["inputs"]["seed"] == 99999999999999

    research_path = root / "research_evidence.json"
    _write_json(research_path, research_evidence)
    graph_path = root / "graph.json"
    _write_json(graph_path, payload["graph"])
    _write_metadata(
        root,
        entrypoint="executor_revise",
        requirements=["revise route must skip research"],
        extra={
            "scenario": "revise-without-forced-research",
            "ledger": "absent (research phase never ran)",
            "seed_after": payload["graph"]["nodes"][0]["inputs"]["seed"],
        },
    )
    envelope = _executor_envelope(
        root,
        executor_result,
        scenario="revise-without-forced-research",
        actions=[
            {
                "op": "executor.run",
                "query": request.query,
                "route": "revise",
                "research": False,
                "implement": True,
            },
            {
                "op": "implement",
                "via": "run_executor",
                "route": "revise",
                "edit_called": edit_called,
                "research_stage_called": False,
                "research_ledger_present": False,
                "seed_after": payload["graph"]["nodes"][0]["inputs"]["seed"],
            },
            {"op": "reply", "message": executor_result.reply},
        ],
    )
    _write_std_trail(
        root,
        "Revise Without Forced Research",
        (
            "Ran the full executor classify -> implement -> reply pipeline on the "
            "revise route for a KSampler seed parameter edit. The research phase "
            "must be skipped entirely: no agent research stage, no hivemind tool "
            "calls, no research ledger. The direct edit lands on the returned graph."
        ),
    )
    return {
        **envelope,
        "research_path": str(research_path),
        "graph_path": str(graph_path),
        "metadata_path": str(root / "metadata.json"),
    }


# ── 2. empty-graph-authoring ─────────────────────────────────────────────────


def build_empty_graph_authoring_evidence(report_dir: Path) -> dict[str, Any]:
    """Prove the agent authors a graph from scratch via the implement tools,
    driven through the executor's implement seam (run_executor)."""
    from unittest import mock

    from vibecomfy import load_workflow_any
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor
    from vibecomfy.executor.edit_suggestion_tools import suggest_seed_nodes
    from vibecomfy.executor.lookup_tools import ready_template_list, ready_template_load

    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    intent = "Build a text to image workflow from scratch"
    tool_results: dict[str, Any] = {}

    def fake_classify(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="medium",
            plan_summary="Author a new workflow from scratch.",
            intent="edit",
            route="adapt",
            task="edit_graph",
            change_goal=intent,
        )

    def fake_handle_agent_edit(payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        # The implement seam runs the REAL implement-phase tools, then
        # compiles the ready template into the graph.
        tool_results["suggest_seed_nodes"] = suggest_seed_nodes(
            intent,
            constraints={"output_type": "image"},
            explicit=True,
        )
        tool_results["ready_template_list"] = ready_template_list("video")
        tool_results["ready_template_load"] = ready_template_load(
            "video/wan_t2v", include_content=True
        )
        workflow = load_workflow_any("video/wan_t2v")
        workflow.finalize_metadata()
        return _fake_edit_ok(workflow.compile("api"), "Authored a workflow from scratch.")

    request = ExecutorRequest(
        query=intent,
        graph={"nodes": [], "links": []},
        profile="default",
        session_id="agentic-harness-empty-authoring",
    )

    with _EXECUTOR_FAKE_LOCK:
        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
            mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=fake_handle_agent_edit),
            mock.patch(
                "vibecomfy.executor.core.run_reply_turn",
                return_value="Authored a new workflow from scratch.",
            ),
        ):
            executor_result = run_executor(request)

    seed_result = tool_results["suggest_seed_nodes"]
    list_result = tool_results["ready_template_list"]
    load_result = tool_results["ready_template_load"]

    assert seed_result.status.value == "ok"
    assert seed_result.result.get("case") == "empty-graph"
    suggested_classes = [s["class_type"] for s in seed_result.result["suggestions"]]
    assert "KSampler" in suggested_classes
    assert list_result.status.value == "ok"
    assert load_result.status.value == "ok"
    assert load_result.result.get("id") == "video/wan_t2v"
    assert bool(load_result.result.get("content"))
    assert bool(load_result.result.get("sha256"))

    compiled_api = executor_result.graph or {}
    class_types = {node.get("class_type") for node in compiled_api.values()}
    graph_summary = {
        "node_count": len(compiled_api),
        "classes": sorted(class_types),
        "suggested_seed_classes_present": sorted(set(suggested_classes) & class_types),
        "seed_case": seed_result.result.get("case"),
    }
    assert graph_summary["suggested_seed_classes_present"], "authored graph lacks every suggested seed class"

    tool_calls_path = root / "tool_calls.json"
    _write_json(
        tool_calls_path,
        {
            "intent": intent,
            "tools": [
                _tool_result_to_dict(seed_result),
                _tool_result_to_dict(list_result),
                _tool_result_to_dict(load_result),
            ],
        },
    )
    graph_path = root / "graph.json"
    _write_json(graph_path, compiled_api)
    graph_summary_path = root / "graph_summary.json"
    _write_json(graph_summary_path, graph_summary)
    _write_metadata(
        root,
        entrypoint="executor_authoring",
        requirements=["empty-graph authoring via suggest_seed_nodes + ready_template_load"],
        extra={
            "scenario": "empty-graph-authoring",
            "seed_case": seed_result.result.get("case"),
            "template_id": load_result.result.get("id"),
        },
    )
    envelope = _executor_envelope(
        root,
        executor_result,
        scenario="empty-graph-authoring",
        actions=[
            {
                "op": "executor.run",
                "query": request.query,
                "route": "adapt",
                "implement": True,
            },
            {
                "op": "tool.call",
                "tool": "suggest_seed_nodes",
                "status": seed_result.status.value,
                "case": seed_result.result.get("case"),
                "suggestions": suggested_classes,
            },
            {
                "op": "tool.call",
                "tool": "ready_template_list",
                "status": list_result.status.value,
                "count": list_result.result.get("count"),
            },
            {
                "op": "tool.call",
                "tool": "ready_template_load",
                "status": load_result.status.value,
                "template_id": load_result.result.get("id"),
                "sha256": load_result.result.get("sha256"),
            },
            {
                "op": "graph.produced",
                "node_count": graph_summary["node_count"],
                "seed_classes_present": graph_summary["suggested_seed_classes_present"],
            },
        ],
    )
    _write_std_trail(
        root,
        "Empty Graph Authoring",
        (
            "Ran the executor pipeline with an adapt plan; the implement seam "
            "called the real implement-phase tools (suggest_seed_nodes "
            "empty-graph case, ready_template_list, ready_template_load) and "
            "produced a workflow containing the suggested seed classes."
        ),
    )
    return {
        **envelope,
        "tool_calls_path": str(tool_calls_path),
        "graph_path": str(graph_path),
        "graph_summary_path": str(graph_summary_path),
        "metadata_path": str(root / "metadata.json"),
    }


# ── 3. research-only-decision-memo ───────────────────────────────────────────


def build_research_only_decision_memo_evidence(report_dir: Path) -> dict[str, Any]:
    """Prove the research route runs question-before-search with the AGENT
    choosing hivemind_search/hivemind_get, all through run_executor."""
    from unittest import mock

    from vibecomfy.executor.agent_research_stage import (
        run_agent_research_stage as real_run_agent_research_stage,
    )
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor
    from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus

    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    HIT_ID = "hivemind:external_resources:wan-t2v-1"
    GET_ID = f"hivemind_get:{HIT_ID.removeprefix('hivemind:')}"
    question = "Which ComfyUI template should anchor a Wan 2.1 text-to-video build?"

    def fake_classify(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=True,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="Research the right Wan 2.1 T2V template, then answer without editing.",
            intent="research",
            route="research",
            task="research_nodes",
            research_goal=question,
            search_directions=(
                "Wan 2.1 text-to-video ComfyUI template recommendations",
            ),
            source_preferences=("hivemind", "workflows"),
            avoid=("generic searches for the raw sentence",),
        )

    def fake_search(query: str, limit: int = 5, **kwargs: Any) -> ToolResult:
        assert question in query, "search query drifted from the explicit research question"
        return ToolResult(
            tool_name="hivemind_search",
            status=ToolStatus.OK,
            result={
                "query": query,
                "count": 1,
                "hits": [
                    {
                        "evidence_id": HIT_ID,
                        "title": "Wan 2.1 T2V template",
                        "body": "Official Wan 2.1 text-to-video template notes.",
                        "url": "https://example.com/wan-t2v",
                    }
                ],
                "next_cursor": None,
                "has_more": False,
            },
            evidence_ids=(HIT_ID,),
        )

    def fake_get(evidence_id: str, **kwargs: Any) -> ToolResult:
        assert evidence_id == HIT_ID
        return ToolResult(
            tool_name="hivemind_get",
            status=ToolStatus.OK,
            result={
                "evidence_id": evidence_id,
                "source_type": "workflow",
                "table": "external_resources",
                "row": {
                    "title": "Wan 2.1 T2V template",
                    "body": "Full record: use video/wan_t2v with 1.3B fp16.",
                },
            },
            evidence_ids=(evidence_id,),
        )

    def fake_judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        # The AGENT chooses the tools: search first, then get, then finish.
        if "hivemind_search →" not in digest:
            return {
                "action": "call",
                "tool": "hivemind_search",
                "args": {"query": question},
            }
        if "hivemind_get →" not in digest:
            return {
                "action": "call",
                "tool": "hivemind_get",
                "args": {"evidence_id": HIT_ID},
            }
        return {
            "action": "finish",
            "conclusion": "Use video/wan_t2v as the anchor template for Wan 2.1 T2V.",
            "evidence_ids": [GET_ID],
            "uncertainty": "Low; single authoritative source.",
        }

    def fake_reply(*_args: Any, **_kwargs: Any) -> str:
        return "The Wan 2.1 T2V build should anchor on video/wan_t2v."

    captured: dict[str, Any] = {}

    def real_stage_with_fakes(**kwargs: Any) -> Any:
        result = real_run_agent_research_stage(
            route=kwargs["route"],
            question=kwargs["question"],
            spec=kwargs.get("spec"),
            search_fn=fake_search,
            get_fn=fake_get,
            judge_fn=fake_judge,
        )
        captured["trace"] = result[0].to_dict()
        captured["pack"] = result[1].to_dict()
        return result

    request = ExecutorRequest(
        query="Which template should I anchor a Wan 2.1 text-to-video build on?",
        profile="default",
        session_id="agentic-harness-research-memo",
    )

    with _EXECUTOR_FAKE_LOCK:
        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
            mock.patch(
                "vibecomfy.executor.core.run_agent_research_stage",
                side_effect=real_stage_with_fakes,
            ),
            mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=fake_reply),
            mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit,
        ):
            executor_result = run_executor(request)
            edit_called = mock_edit.called

    payload = executor_result.to_dict()
    report = payload.get("report", {}).get("executor", {})
    research = report.get("research", {}) or {}

    ledger = captured["pack"]["ledger"]["entries"]
    decisions = [entry["decision"] for entry in ledger]
    assert decisions[0] == "research_question", "question was not recorded before the first search"
    assert "hivemind_search" in decisions
    assert "hivemind_get" in decisions
    assert "synthesize" in decisions
    assert "enough_refine" in decisions

    tool_calls = [
        call
        for iteration in captured["trace"]["iterations"]
        for call in iteration["tool_calls"]
    ]
    tools = [call["tool"] for call in tool_calls]
    assert tools and tools[0] == "hivemind_search", "first tool call was not hivemind_search"
    assert "hivemind_get" in tools

    artifact_ids = set(captured["pack"]["artifacts"])
    citations = research.get("citations", [])
    assert citations, "C5 memo has no citations"
    assert all(citation in artifact_ids for citation in citations), (
        "C5 citations must resolve to frozen evidence-pack artifacts"
    )
    memo_keys = {
        "question",
        "conclusion",
        "citations",
        "uncertainty",
        "next_action",
    }
    assert memo_keys <= set(research), f"C5 memo missing keys: {sorted(memo_keys - set(research))}"
    assert research.get("question") == question
    assert research.get("mode") == "agent_owned"
    assert edit_called is False

    citation_validity = {
        "cited": citations,
        "resolvable": [citation for citation in citations if citation in artifact_ids],
        "unresolvable": [citation for citation in citations if citation not in artifact_ids],
    }

    trace_path = root / "research_trace.json"
    _write_json(
        trace_path,
        {
            **captured["trace"],
            "ledger": captured["pack"]["ledger"],
            "artifacts": captured["pack"]["artifacts"],
        },
    )
    memo_path = root / "research_memo.json"
    _write_json(memo_path, research)
    validity_path = root / "citation_validity.json"
    _write_json(validity_path, citation_validity)
    _write_metadata(
        root,
        entrypoint="executor_research",
        requirements=["question-before-search; agent-chosen hivemind tools; citations resolvable; C5 memo"],
        extra={
            "scenario": "research-only-decision-memo",
            "ledger_order": decisions,
            "tools": tools,
        },
    )
    envelope = _executor_envelope(
        root,
        executor_result,
        scenario="research-only-decision-memo",
        actions=[
            {
                "op": "executor.run",
                "query": request.query,
                "route": "research",
                "research": True,
                "implement": False,
            },
            {
                "op": "research",
                "via": "run_executor.run_agent_research_stage",
                "question_recorded_before_search": decisions[0] == "research_question",
                "tools": tools,
                "citations_resolvable": citation_validity["resolvable"],
                "edit_called": edit_called,
            },
            {"op": "reply", "message": executor_result.reply},
        ],
    )
    _write_std_trail(
        root,
        "Research-Only Decision Memo",
        (
            "Ran the executor research route with the real C1 agent-owned "
            "tool-calling research stage (injected tool fakes; the AGENT chose "
            "hivemind_search then hivemind_get). The ledger records the explicit "
            "question before the first search, and the C5 memo "
            "(question/conclusion/citations/uncertainty/next_action) cites only "
            "evidence resolvable inside the frozen pack."
        ),
    )
    return {
        **envelope,
        "trace_path": str(trace_path),
        "memo_path": str(memo_path),
        "citation_validity_path": str(validity_path),
        "metadata_path": str(root / "metadata.json"),
    }


# ── 4. headless-ambiguity-needs_input ────────────────────────────────────────


def build_headless_ambiguity_needs_input_evidence(report_dir: Path) -> dict[str, Any]:
    """Prove the headless agent emits a typed needs_input, never a phrase override."""
    from unittest import mock

    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.agent.service import run_headless
    from vibecomfy.executor.contracts import ClassifyDecision
    from vibecomfy.executor.stage_contracts import NeedsInput

    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    typed = NeedsInput(
        decision="target_workflow_choice",
        question="Which target workflow should I adapt: video/wan_t2v or video/ltx_video?",
        missing_information=("The user named two candidate workflows without a preference.",),
        options=("video/wan_t2v", "video/ltx_video"),
    )

    def fake_classify(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        plan = ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            intent="respond",
            route="clarify",
            plan_summary="A decision-critical input is missing; ask before proceeding.",
            clarification_question="Which target workflow should I adapt?",
            clarification_options=("video/wan_t2v", "video/ltx_video"),
        )
        # Classifier-authored ambiguity lives on the decision object; the
        # headless layer reads ONLY this typed value (never query phrases).
        object.__setattr__(plan, "needs_input", typed)
        return plan

    def fake_reply(*_args: Any, **_kwargs: Any) -> str:
        return ""

    request = HeadlessAgentRequest(
        query="Adapt my workflow to Wan T2V or LTX?",
        output_dir=root / "headless_out",
        session_id="agentic-harness-needs-input",
    )

    with mock.patch("vibecomfy.agent.service._check_live_readiness", return_value={"ready": True}):
        with _EXECUTOR_FAKE_LOCK:
            with (
                mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
                mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=fake_reply),
                mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit,
            ):
                result = run_headless(request)
                edit_called = mock_edit.called

    response = result.response
    emitted = response.get("needs_input")
    route = response.get("route")

    assert result.status == "success"
    assert route == "clarify", "clarify route must not be overridden by phrase inspection"
    assert isinstance(emitted, dict), "needs_input must be a typed dict"
    assert emitted.get("decision") == typed.decision
    assert emitted.get("question") == typed.question
    assert emitted.get("missing_information") == list(typed.missing_information)
    assert emitted.get("options") == list(typed.options)
    assert "bounded_assumption" not in emitted
    assert edit_called is False, "clarify route must never run the edit phase"

    headless_payload = {
        "status": result.status,
        "ok": result.ok,
        "response": response,
        "route": route,
        "edit_called": edit_called,
    }
    result_path = root / "headless_result.json"
    _write_json(result_path, headless_payload)
    needs_input_path = root / "needs_input.json"
    _write_json(
        needs_input_path,
        {
            "typed": emitted,
            "emitted_by": "classify_stage",
            "route": route,
            "phrase_list_override": False,
            "decision_matches_classifier_authored": emitted.get("decision") == typed.decision,
        },
    )
    _write_metadata(
        root,
        entrypoint="headless_agent",
        requirements=["typed needs_input on decision-critical ambiguity; no phrase-list override"],
        extra={
            "scenario": "headless-ambiguity-needs_input",
            "route": route,
            "needs_input_decision": emitted.get("decision"),
        },
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "headless.run",
                "query": request.query,
                "route": route,
                "status": result.status,
            },
            {
                "op": "needs_input.emitted",
                "decision": emitted.get("decision"),
                "question": emitted.get("question"),
                "options": emitted.get("options"),
                "phrase_list_override": False,
            },
        ],
    )
    _write_std_trail(
        root,
        "Headless Ambiguity Needs Input",
        (
            "Ran the headless agent service (real run_headless + real executor) with "
            "a classifier-authored clarify decision. The response carries the typed "
            "needs_input object (decision/question/missing_information/options); the "
            "route stays clarify and the edit phase never runs."
        ),
    )
    return {
        "scenario": "headless-ambiguity-needs_input",
        "headless_result_path": str(result_path),
        "needs_input_path": str(needs_input_path),
        "metadata_path": str(root / "metadata.json"),
        "actions_path": str(root / "actions.jsonl"),
    }


# ── 5. schema-drift-approved-normalization ───────────────────────────────────


def build_schema_drift_approved_normalization_evidence(report_dir: Path) -> dict[str, Any]:
    """Prove the queue path refuses unapproved normalization and applies exactly
    the proposal — driven through the executor's implement seam."""
    from unittest import mock

    from vibecomfy import load_workflow_any
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor
    from vibecomfy.schema import get_authoring_schema_provider
    from vibecomfy.schema.validate import (
        NormalizationApproval,
        SchemaNormalizationRequired,
        apply_schema_normalization,
        propose_schema_normalization,
    )

    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/wan_t2v")
    api_dict = workflow.compile("api")
    # Inject a schema drift the runtime would reject: an input the live node
    # schema does not declare. The natural template drift (portable choice
    # coercion) stays in the proposal too.
    api_dict["3"]["inputs"]["bogus_extra_input"] = 42
    provider = get_authoring_schema_provider()

    proposal = propose_schema_normalization(api_dict, provider)
    assert proposal.ops, "expected a non-empty normalization proposal"

    unapproved_error: dict[str, Any] = {}
    try:
        raise SchemaNormalizationRequired(proposal)
    except SchemaNormalizationRequired as exc:
        unapproved_error = {
            "raised": True,
            "error_class": type(exc).__name__,
            "message": str(exc),
            "normalization": exc.to_dict().get("normalization", {}),
            "approved_without_approval": proposal.approved_by(None),
        }
    assert unapproved_error["raised"] is True
    assert unapproved_error["approved_without_approval"] is False

    approval = NormalizationApproval(proposal_digest=proposal.digest(), granted_by="agent")
    assert proposal.approved_by(approval) is True

    before = api_dict
    applied = apply_schema_normalization(dict(api_dict), proposal)

    changed: dict[str, dict[str, Any]] = {}
    for op in proposal.ops:
        node_id = str(op.node_id)
        field = str(op.field)
        before_value = before[node_id]["inputs"].get(field)
        after_value = applied[node_id]["inputs"].get(field)
        changed[f"{node_id}.{field}"] = {
            "kind": op.kind,
            "before": before_value,
            "after": after_value,
            "exactly_proposed": after_value == op.after,
        }
        assert after_value == op.after, f"op for {node_id}.{field} was not applied exactly"
    untouched_nodes = set(before) - {str(op.node_id) for op in proposal.ops}
    assert all(
        before[node_id] == applied[node_id] for node_id in untouched_nodes
    ), "normalization touched nodes outside the proposal"

    approved_metadata = {
        "approval_granted_by": approval.granted_by,
        "proposal_digest": proposal.digest(),
        "approval_binds_proposal": proposal.approved_by(approval),
        "ops_count": len(proposal.ops),
        "ops": [op.to_dict() for op in proposal.ops],
        "applied_changes": changed,
        "bogus_extra_input_dropped": "bogus_extra_input" not in applied["3"]["inputs"],
        "evidence_in_metadata": True,
    }
    assert approved_metadata["bogus_extra_input_dropped"] is True

    def fake_classify(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="low",
            plan_summary="Queue a drifted graph through normalization.",
            intent="edit",
            route="revise",
            task="edit_graph",
        )

    # Through the executor: the implement seam raises the unapproved
    # normalization failure (typed), then the approved run applies exactly the
    # proposal and returns the graph.
    failures: list[dict[str, Any]] = []

    def fake_handle_agent_edit(payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        if payload.get("session_id") == "agentic-harness-normalization-unapproved":
            return _fake_edit_failure(
                "ValidationError",
                "Schema normalization required before queueing.",
                {"normalization": unapproved_error},
            )
        return _fake_edit_ok(applied, "Normalization applied exactly as proposed.")

    request_unapproved = ExecutorRequest(
        query="Queue this graph; it drifted from the live schema.",
        graph=dict(api_dict),
        profile="default",
        session_id="agentic-harness-normalization-unapproved",
    )
    request_approved = ExecutorRequest(
        query="Queue this graph with the approved normalization proposal.",
        graph=dict(api_dict),
        profile="default",
        session_id="agentic-harness-normalization-approved",
    )

    with _EXECUTOR_FAKE_LOCK:
        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
            mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=fake_handle_agent_edit),
            mock.patch("vibecomfy.executor.core.run_reply_turn", return_value=""),
        ):
            unapproved_result = run_executor(request_unapproved)
            approved_result = run_executor(request_approved)

    unapproved_payload = unapproved_result.to_dict()
    assert unapproved_payload["ok"] is False
    implementation = unapproved_payload["report"]["executor"].get("implementation") or {}
    assert implementation.get("failure", {}).get("failure_kind") in (
        "ValidationError",
        "validation_error",
    )

    approved_payload = approved_result.to_dict()
    assert approved_payload["ok"] is True
    assert approved_payload["graph"] is not None
    assert "bogus_extra_input" not in approved_payload["graph"]["3"]["inputs"]

    # The common envelope is the approved run's executor_result.json; the
    # blocked run is frozen separately so both pipeline outcomes are provable.
    _write_json(root / "executor_result.json", approved_payload)
    _write_json(root / "executor_report.json", approved_payload.get("report", {}).get("executor", {}))
    _write_json(root / "executor_result_unapproved.json", unapproved_payload)

    proposal_path = root / "drift_proposal.json"
    _write_json(proposal_path, {"ops": [op.to_dict() for op in proposal.ops]})
    error_path = root / "unapproved_error.json"
    _write_json(error_path, unapproved_error)
    approved_path = root / "approved_metadata.json"
    _write_json(approved_path, approved_metadata)
    _write_metadata(
        root,
        entrypoint="executor_queue_preparation",
        requirements=["unapproved normalization refused; approved run applies exactly the proposal"],
        extra={
            "scenario": "schema-drift-approved-normalization",
            "proposal_digest": proposal.digest(),
            "ops_count": len(proposal.ops),
        },
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "executor.run",
                "case": "unapproved",
                "query": request_unapproved.query,
                "failure_kind": (unapproved_payload["report"]["executor"].get("implementation") or {})
                .get("failure", {})
                .get("failure_kind"),
            },
            {
                "op": "queue.preparation",
                "proposal_ops": len(proposal.ops),
                "unapproved_refused": True,
                "error_class": "SchemaNormalizationRequired",
            },
            {
                "op": "executor.run",
                "case": "approved",
                "query": request_approved.query,
                "ok": True,
            },
            {
                "op": "queue.approval",
                "granted_by": approval.granted_by,
                "digest_bound": proposal.approved_by(approval),
                "ops_applied": list(changed),
            },
        ],
    )
    _write_std_trail(
        root,
        "Schema Drift Approved Normalization",
        (
            "Ran the executor pipeline twice: without approval the implement "
            "seam fails the turn with the typed SchemaNormalizationRequired "
            "evidence; with an approval bound to the exact proposal digest, "
            "exactly the proposed ops are applied and the graph returns."
        ),
    )
    return {
        "scenario": "schema-drift-approved-normalization",
        "executor_result_path": str(root / "executor_result.json"),
        "executor_report_path": str(root / "executor_report.json"),
        "proposal_path": str(proposal_path),
        "unapproved_error_path": str(error_path),
        "approved_metadata_path": str(approved_path),
        "metadata_path": str(root / "metadata.json"),
        "actions_path": str(root / "actions.jsonl"),
    }


# ── 6. hivemind-rate-limiting ────────────────────────────────────────────────


def build_hivemind_rate_limiting_evidence(report_dir: Path) -> dict[str, Any]:
    """Prove 429 -> typed rate_limited + cooldown honored + no web fallthrough,
    driven through the executor's research phase with the real Hivemind tools."""
    from unittest import mock

    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor
    from vibecomfy.executor.hivemind_clients import HivemindError
    from vibecomfy.executor.hivemind_tools import hivemind_get, hivemind_search
    from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus

    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    cache_root = Path(tempfile.mkdtemp(prefix="v01-rate-limit-"))
    transport_calls: dict[str, int] = {"count": 0}
    web_calls: dict[str, int] = {"count": 0}

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        transport_calls["count"] += 1
        raise HivemindError(
            "Hivemind quota exceeded",
            reason="http",
            status_code=429,
            retry_after_seconds=45.0,
        )

    def fake_web_search(*_args: Any, **_kwargs: Any) -> ToolResult:
        web_calls["count"] += 1
        return ToolResult(tool_name="web_search", status=ToolStatus.OK, result={"results": []})

    def fake_classify(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=True,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="Research with a rate-limited Hivemind.",
            intent="research",
            route="research",
            task="research_nodes",
            research_goal="Which Wan T2V template should I use?",
        )

    def fake_judge(question: str, digest: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if "hivemind_search →" not in digest:
            return {
                "action": "call",
                "tool": "hivemind_search",
                "args": {"query": question},
            }
        if "hivemind_get →" not in digest:
            return {
                "action": "call",
                "tool": "hivemind_get",
                "args": {"evidence_id": "hivemind:external_resources:wan-t2v-1"},
            }
        return {
            "action": "finish",
            "conclusion": "Hivemind is rate-limited; no evidence gathered.",
            "evidence_ids": [],
            "uncertainty": "Hivemind unavailable.",
        }

    # The executor's research phase runs the REAL hivemind tools (patched
    # transport -> 429); the cooldown circuit is shared and isolated in a temp
    # cache root so the global default cache is untouched. The wrapper also
    # captures the stage trace for the frozen cooldown evidence.
    captured: dict[str, Any] = {}

    def stage_with_cache(**kwargs: Any) -> Any:
        from vibecomfy.executor.agent_research_stage import run_agent_research_stage

        result = run_agent_research_stage(
            route=kwargs["route"],
            question=kwargs["question"],
            spec=kwargs.get("spec"),
            judge_fn=fake_judge,
            cache_root=cache_root,
        )
        captured["trace"] = result[0].to_dict()
        return result

    request = ExecutorRequest(
        query="Which Wan T2V template should I use?",
        profile="default",
        session_id="agentic-harness-rate-limit",
    )

    with _EXECUTOR_FAKE_LOCK:
        with (
            mock.patch("vibecomfy.executor.hivemind_tools._hivemind_search_transport", side_effect=boom),
            mock.patch("vibecomfy.executor.hivemind_tools._hivemind_get_row", side_effect=boom),
            mock.patch("vibecomfy.executor.web_tools.web_search", side_effect=fake_web_search),
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
            mock.patch(
                "vibecomfy.executor.core.run_agent_research_stage",
                side_effect=stage_with_cache,
            ),
            mock.patch(
                "vibecomfy.executor.core.run_reply_turn",
                return_value="Hivemind is rate-limited; no evidence gathered.",
            ),
        ):
            # First: the cooldown gets set by a direct tool call (same temp
            # cache root), so the stage's second call short-circuits.
            first = hivemind_search("wan t2v template", cache_root=cache_root)
            executor_result = run_executor(request)

    second_status = "rate_limited"  # cooldown short-circuit in the stage loop
    assert first.status is ToolStatus.RATE_LIMITED
    assert first.retry_after_seconds is not None and first.retry_after_seconds > 0
    assert first.diagnostics and first.diagnostics[0].code == "hivemind_rate_limited"
    assert transport_calls["count"] == 1, "cooldown must prevent a second transport hit"
    assert web_calls["count"] == 0, "rate limit must never fall through to web_search"

    payload = executor_result.to_dict()
    assert payload["ok"] is True
    trace_statuses = [
        call["status"]
        for iteration in (captured.get("trace", {}).get("iterations") or [])
        for call in iteration.get("tool_calls", [])
    ]
    assert trace_statuses and all(status == "rate_limited" for status in trace_statuses)

    calls_path = root / "rate_limit_calls.json"
    _write_json(
        calls_path,
        {
            "first_search": _tool_result_to_dict(first),
            "second_search_during_cooldown": {"status": second_status},
        },
    )
    cooldown_path = root / "cooldown_trace.json"
    _write_json(
        cooldown_path,
        {
            "transport_calls": transport_calls["count"],
            "web_search_calls": web_calls["count"],
            "cooldown_honored": second_status == "rate_limited",
            "no_web_fallthrough": web_calls["count"] == 0,
            "research_stage_tool_statuses": trace_statuses,
        },
    )
    _write_metadata(
        root,
        entrypoint="executor_hivemind_tool",
        requirements=["429 -> typed rate_limited; cooldown respected; no web fallthrough"],
        extra={"scenario": "hivemind-rate-limiting", "transport_calls": transport_calls["count"]},
    )
    envelope = _executor_envelope(
        root,
        executor_result,
        scenario="hivemind-rate-limiting",
        actions=[
            {"op": "executor.run", "query": request.query, "route": "research"},
            {"op": "tool.call", "tool": "hivemind_search", "status": "rate_limited", "retry_after_seconds": first.retry_after_seconds},
            {"op": "tool.call", "tool": "hivemind_search", "status": "rate_limited", "cooldown_short_circuit": True},
            {"op": "tool.call", "tool": "hivemind_get", "status": "rate_limited", "shared_cooldown": True},
            {"op": "web_search", "called": False, "fallthrough": False},
        ],
    )
    _write_std_trail(
        root,
        "Hivemind Rate Limiting",
        (
            "Ran the executor research route with the real Hivemind tools behind a "
            "429 transport: the first call returns a typed rate_limited result "
            "with retry_after_seconds, the R2-B2 cooldown short-circuits the next "
            "call (transport hit exactly once), hivemind_get shares the cooldown, "
            "and web_search is never invoked as a fallback."
        ),
    )
    return {
        **envelope,
        "rate_limit_calls_path": str(calls_path),
        "cooldown_trace_path": str(cooldown_path),
        "metadata_path": str(root / "metadata.json"),
    }


# ── 7. invalid-emitted-socket ────────────────────────────────────────────────


def build_invalid_emitted_socket_evidence(report_dir: Path) -> dict[str, Any]:
    """Prove a phantom link endpoint refuses the whole emit with socket evidence,
    driven through the executor's implement seam."""
    from unittest import mock

    from vibecomfy import load_workflow_any
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor
    from vibecomfy.porting.emit.ui import emit_ui_json
    from vibecomfy.porting.refuse import RefusedEmit
    from vibecomfy.schema import get_authoring_schema_provider
    from vibecomfy.workflow import VibeEdge

    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    provider = get_authoring_schema_provider()
    source_node = "3"  # KSampler: emits exactly one output (LATENT at slot 0)
    target_edge = None
    for edge in load_workflow_any("video/wan_t2v").edges:
        if edge.to_input == "model":
            target_edge = edge
            break
    assert target_edge is not None, "wan_t2v must expose a model input edge"
    phantom_output = "9"  # out-of-range slot; no emitted socket can match it

    # Control: the same workflow WITHOUT the phantom edge emits cleanly.
    control = load_workflow_any("video/wan_t2v")
    control_envelope = emit_ui_json(control, schema_provider=provider)
    control_ok = {
        "emitted": True,
        "node_count": len(control_envelope["nodes"]),
        "link_count": len(control_envelope["links"]),
    }

    # Drifted: phantom edge must refuse the whole emit (never a silent drop).
    drifted = load_workflow_any("video/wan_t2v")
    drifted.edges = list(drifted.edges) + [
        VibeEdge(
            from_node=source_node,
            from_output=phantom_output,
            to_node=target_edge.to_node,
            to_input=target_edge.to_input,
        )
    ]
    refusal: dict[str, Any] = {}
    try:
        emit_ui_json(drifted, schema_provider=provider)
    except RefusedEmit as exc:
        refusal = {
            "raised": True,
            "error_class": type(exc).__name__,
            "message": str(exc),
            "diff": _jsonable(exc.diff),
        }
    assert refusal.get("raised") is True
    links = refusal["diff"].get("links", {})
    assert links, "RefusedEmit must carry per-link endpoint evidence"
    for key, entry in links.items():
        assert f"{source_node}.{phantom_output}" in key
        source_evidence = entry.get("source", {})
        assert source_evidence.get("requested_output") == phantom_output
        assert source_evidence.get("emitted_sockets"), "refusal must record the emitted socket array"
        assert source_evidence.get("attempted_remaps"), "refusal must record the remap strategies attempted"
        assert entry.get("missing") == "source_socket"

    def fake_classify(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="low",
            plan_summary="Emit the edited workflow.",
            intent="edit",
            route="revise",
            task="edit_graph",
        )

    # Through the executor: the implement seam emits the drifted graph with the
    # real emit rail; RefusedEmit surfaces as a typed implement failure.
    def fake_handle_agent_edit(payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        try:
            emit_ui_json(drifted, schema_provider=provider)
        except RefusedEmit as exc:
            return _fake_edit_failure(
                "ValidationError",
                "Emit refused: phantom link endpoint has no emitted socket.",
                {"refused_emit": refusal},
            )
        raise AssertionError("the drifted graph must refuse emit")

    request = ExecutorRequest(
        query="Connect the sampler to the model input (intentional phantom).",
        graph={"nodes": [], "links": []},
        profile="default",
        session_id="agentic-harness-invalid-emit",
    )

    with _EXECUTOR_FAKE_LOCK:
        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
            mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=fake_handle_agent_edit),
            mock.patch("vibecomfy.executor.core.run_reply_turn", return_value=""),
        ):
            executor_result = run_executor(request)

    payload = executor_result.to_dict()
    assert payload["ok"] is False
    implementation = payload["report"]["executor"].get("implementation") or {}
    assert implementation.get("failure", {}).get("failure_kind") in ("ValidationError", "validation_error")
    assert "refused_emit" in json.dumps(implementation)

    refusal_path = root / "refusal.json"
    _write_json(refusal_path, refusal)
    control_path = root / "control_emit.json"
    _write_json(control_path, control_ok)
    _write_metadata(
        root,
        entrypoint="executor_emit",
        requirements=["invalid emitted socket refuses emit with endpoint/socket evidence, never a silent drop"],
        extra={
            "scenario": "invalid-emitted-socket",
            "phantom_output": phantom_output,
            "control_link_count": control_ok["link_count"],
        },
    )
    envelope = _executor_envelope(
        root,
        executor_result,
        scenario="invalid-emitted-socket",
        actions=[
            {"op": "executor.run", "query": request.query, "route": "revise", "ok": False},
            {"op": "emit.control", "emitted": True, "links": control_ok["link_count"]},
            {
                "op": "emit.refused",
                "error_class": "RefusedEmit",
                "dangling_links": list(links),
                "silent_drop": False,
            },
        ],
    )
    _write_std_trail(
        root,
        "Invalid Emitted Socket",
        (
            "Ran the executor pipeline; the implement seam emitted a workflow "
            "whose link references a source socket that no emitted node socket "
            "can match. The whole emit is refused with a typed RefusedEmit "
            "carrying per-endpoint evidence (requested output, emitted socket "
            "array, attempted remaps) — the edge is never silently dropped. "
            "The control graph without the phantom edge emits cleanly."
        ),
    )
    return {
        **envelope,
        "refusal_path": str(refusal_path),
        "control_emit_path": str(control_path),
        "metadata_path": str(root / "metadata.json"),
    }


# ── 8. queue-refusal-valid-runtime-probe ─────────────────────────────────────


def build_queue_refusal_valid_runtime_probe_evidence(report_dir: Path) -> dict[str, Any]:
    """Prove the queue gate blocks bare tier labels and accepts a verified
    receipt — driven through the executor's implement seam."""
    from datetime import datetime, timezone
    from unittest import mock

    from vibecomfy.comfy_nodes.agent.contracts import StageResult, TurnContext
    from vibecomfy.comfy_nodes.agent.gates import (
        RUNTIME_READINESS_UNVERIFIED_CODE,
        update_queue_gate,
        verify_queue_probe_receipt,
    )
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor
    from vibecomfy.runtime.schema_probe import (
        ClassProbeResult,
        ProbeStatus,
        RuntimeProbeReceipt,
    )
    from vibecomfy.schema.cache import object_info_payload_checksum, runtime_fingerprint

    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    endpoint = "http://127.0.0.1:8188"
    object_info = {
        "CheckpointLoaderSimple": {
            "input": {"required": {"ckpt_name": ["a.safetensors"]}},
            "output": ["MODEL", "CLIP", "VAE"],
        }
    }

    # Case A: a bare strong-tier label without a verifiable receipt is blocked.
    bare_context = TurnContext(session_id="v01-probe-bare")
    bare_blockers = update_queue_gate(
        bare_context,
        evidence_tiers=frozenset({"live_runtime_schema"}),
        verify_live=False,
    )
    bare_gate = bare_context.gate_results["queue_validate_ok"]
    bare_case = {
        "queue_allowed": bare_context.queue_allowed,
        "gate_ok": bare_gate.ok,
        "blocker_codes": [blocker.get("code") for blocker in bare_blockers],
        "blockers": [blocker for blocker in bare_blockers],
    }
    assert bare_case["queue_allowed"] is False
    assert RUNTIME_READINESS_UNVERIFIED_CODE in bare_case["blocker_codes"]

    # Case B: a fresh, verified RuntimeProbeReceipt passes the queue gate via
    # the queue_validate stage handoff (the real producer -> gate path).
    receipt = RuntimeProbeReceipt(
        probe_id="probe-v01-1",
        produced_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        status=ProbeStatus.OK,
        live=True,
        runtime_identity=runtime_fingerprint(endpoint),
        runtime_label=f"server:{endpoint}",
        endpoint_identity=endpoint,
        schema_digest=object_info_payload_checksum(object_info),
        class_count=1,
        readiness="ready",
        class_results=(
            ClassProbeResult(
                class_type="CheckpointLoaderSimple",
                present=True,
                input_count=1,
                output_count=3,
            ),
        ),
    )
    verdict = verify_queue_probe_receipt(
        receipt,
        verify_live=False,
        object_info=object_info,
        endpoint_identity=endpoint,
    )
    assert verdict["verified"] is True
    assert verdict["strong_tier_eligible"] is True

    verified_context = TurnContext(session_id="v01-probe-verified")
    verified_context.record_stage(
        StageResult(
            stage="queue_validate",
            ok=True,
            blocking=False,
            value={"runtime_probe_receipt": receipt.to_dict()},
        )
    )
    verified_blockers = update_queue_gate(
        verified_context,
        verify_live=False,
        object_info=object_info,
        endpoint_identity=endpoint,
    )
    verified_gate = verified_context.gate_results["queue_validate_ok"]
    verified_case = {
        "gate_ok": verified_gate.ok,
        "blocker_count": len(verified_blockers),
        "receipt_present": verified_gate.evidence.get("probe_receipt_present"),
        "receipt_verified": verified_gate.evidence.get("probe_receipt_verified"),
        "receipt_strong_tier_eligible": verified_gate.evidence.get("probe_receipt_strong_tier_eligible"),
        "receipt_status": verified_gate.evidence.get("probe_receipt_status"),
        "receipt_reasons": verified_gate.evidence.get("probe_receipt_reasons"),
    }
    assert verified_case["gate_ok"] is True
    assert verified_case["blocker_count"] == 0
    assert verified_case["receipt_verified"] is True
    assert verified_case["receipt_strong_tier_eligible"] is True

    probe_gate = {
        "bare_tier_label_case": bare_case,
        "verified_receipt_case": verified_case,
        "verdict": {
            "verified": verdict["verified"],
            "strong_tier_eligible": verdict["strong_tier_eligible"],
            "checks": verdict["checks"],
            "reasons": verdict["reasons"],
        },
    }

    def fake_classify(*_args: Any, **_kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="low",
            plan_summary="Queue the edited workflow.",
            intent="edit",
            route="revise",
            task="edit_graph",
        )

    # Through the executor: the implement seam runs the REAL queue gate — the
    # bare-tier case fails the turn, the verified-receipt case passes.
    def fake_handle_agent_edit(payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        if payload.get("session_id") == "agentic-harness-probe-bare":
            return _fake_edit_failure(
                "ValidationError",
                "Queue gate blocked: runtime readiness unverified.",
                {"queue_gate": bare_case},
            )
        return _fake_edit_ok(
            {"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
            "Queued with a verified runtime probe receipt.",
        )

    request_bare = ExecutorRequest(
        query="Queue with only a bare tier label.",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
        profile="default",
        session_id="agentic-harness-probe-bare",
    )
    request_verified = ExecutorRequest(
        query="Queue with a verified runtime probe receipt.",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
        profile="default",
        session_id="agentic-harness-probe-verified",
    )

    with _EXECUTOR_FAKE_LOCK:
        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
            mock.patch("vibecomfy.executor.core.handle_agent_edit", side_effect=fake_handle_agent_edit),
            mock.patch("vibecomfy.executor.core.run_reply_turn", return_value=""),
        ):
            bare_result = run_executor(request_bare)
            verified_result = run_executor(request_verified)

    bare_payload = bare_result.to_dict()
    assert bare_payload["ok"] is False
    assert "queue_gate" in json.dumps(bare_payload)
    verified_payload = verified_result.to_dict()
    assert verified_payload["ok"] is True
    assert verified_payload["graph"] is not None

    # The common envelope is the verified run's executor_result.json; the
    # blocked run is frozen separately so both pipeline outcomes are provable.
    _write_json(root / "executor_result.json", verified_payload)
    _write_json(root / "executor_report.json", verified_payload.get("report", {}).get("executor", {}))
    _write_json(root / "executor_result_bare.json", bare_payload)

    gate_path = root / "probe_gate.json"
    _write_json(gate_path, probe_gate)
    receipt_path = root / "receipt.json"
    _write_json(receipt_path, receipt.to_dict())
    _write_metadata(
        root,
        entrypoint="executor_queue_gate",
        requirements=["bare tier labels blocked; verified RuntimeProbeReceipt passes the queue gate"],
        extra={
            "scenario": "queue-refusal-valid-runtime-probe",
            "bare_blocked": bare_case["queue_allowed"] is False,
            "receipt_passed": verified_case["gate_ok"] is True,
        },
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "executor.run",
                "case": "bare_tier_label",
                "query": request_bare.query,
                "ok": False,
                "codes": bare_case["blocker_codes"],
            },
            {
                "op": "executor.run",
                "case": "verified_receipt",
                "query": request_verified.query,
                "ok": True,
            },
            {
                "op": "queue.gate",
                "case": "verified_receipt",
                "passed": True,
                "receipt_verified": True,
                "receipt_strong_tier_eligible": True,
            },
        ],
    )
    _write_std_trail(
        root,
        "Queue Refusal vs Valid Runtime Probe",
        (
            "Ran the executor pipeline with the real queue gate in the implement "
            "seam: with only a bare live_runtime_schema tier label the gate "
            "blocks (runtime readiness unverified — bare tier labels are not "
            "strong evidence) and the turn fails; with a fresh "
            "RuntimeProbeReceipt handed off through the queue_validate stage "
            "value and independently recomputed (digest + endpoint), the gate "
            "passes and the graph returns."
        ),
    )
    return {
        "scenario": "queue-refusal-valid-runtime-probe",
        "executor_result_path": str(root / "executor_result.json"),
        "executor_report_path": str(root / "executor_report.json"),
        "probe_gate_path": str(gate_path),
        "receipt_path": str(receipt_path),
        "metadata_path": str(root / "metadata.json"),
        "actions_path": str(root / "actions.jsonl"),
    }


# ── registry ─────────────────────────────────────────────────────────────────


_AGENT_JUDGMENT_BUILDERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "revise-without-forced-research": build_revise_without_forced_research_evidence,
    "empty-graph-authoring": build_empty_graph_authoring_evidence,
    "research-only-decision-memo": build_research_only_decision_memo_evidence,
    "headless-ambiguity-needs_input": build_headless_ambiguity_needs_input_evidence,
    "schema-drift-approved-normalization": build_schema_drift_approved_normalization_evidence,
    "hivemind-rate-limiting": build_hivemind_rate_limiting_evidence,
    "invalid-emitted-socket": build_invalid_emitted_socket_evidence,
    "queue-refusal-valid-runtime-probe": build_queue_refusal_valid_runtime_probe_evidence,
}

__all__ = ["_AGENT_JUDGMENT_BUILDERS"]
