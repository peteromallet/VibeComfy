"""HEADLESS HARNESS CONTRACT TESTS."""

from __future__ import annotations

import json
import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


_SPEED_DISTILLATION_SCENARIO = {
    "id": "speed-distillation-research",
    "query": (
        "This video workflow is too slow. Is there a distilled or faster way "
        "to run it without changing the creative intent?"
    ),
}

_GRAPH_EXPLANATION_SCENARIO = {
    "id": "live-graph-explanation-smoke",
    "brief": "briefs/live-graph-explanation-smoke.md",
    "query": (
        "Explain what this graph does. If anything important is missing, ask "
        "one clarifying question; otherwise inspect the workflow and answer directly."
    ),
    "graph": {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd15.safetensors"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": "a quiet studio portrait"},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {"model": ["1", 0], "positive": ["2", 0], "steps": 20, "cfg": 7.0},
        },
    },
}


def _patch_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")

    from vibecomfy.agent import service as svc

    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: {
            "ready": False,
            "route": "openrouter",
            "model": "missing-model",
            "reason": "missing live credentials",
        },
    )


def _write_scenario(scenarios_dir: Path, scenario: dict[str, Any]) -> Path:
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    path = scenarios_dir / f"{scenario['id']}.json"
    path.write_text(json.dumps(scenario), encoding="utf-8")
    return path


def _patch_runner_in_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run harness scenarios in-process instead of in per-scenario subprocesses.

    The harness runner fans out to isolated ``--single`` subprocesses by
    default, which would shield the executor from the deterministic fakes
    these tests install.  The fake subprocess delegates to the runner's own
    in-process ``run_single`` entry point — the exact code path a subprocess
    would execute — so the real headless pipeline still runs, with the
    monkeypatched readiness/executor seams applied.
    """

    def fake_subprocess_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        from tests.live_agentic_harness.runner import run_single

        scenario_path = cmd[cmd.index("--single") + 1]
        tag = cmd[cmd.index("--tag") + 1]
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        output_base = (
            Path(cmd[cmd.index("--output-base") + 1])
            if "--output-base" in cmd
            else None
        )
        run_single(scenario_path, tag, output_base, out_file)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "tests.live_agentic_harness.runner.subprocess.run",
        fake_subprocess_run,
    )


def _fresh_executor_core() -> Any:
    sys.modules.pop("vibecomfy.executor.core", None)
    executor_pkg = sys.modules.get("vibecomfy.executor")
    if executor_pkg is not None and hasattr(executor_pkg, "core"):
        delattr(executor_pkg, "core")
    return importlib.import_module("vibecomfy.executor.core")


def _patch_ready_speed_research(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")

    from vibecomfy.agent import service as svc

    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: {
            "ready": True,
            "route": "openrouter",
            "model": "live-contract-model",
        },
    )

    def fake_run_executor(*args: Any, **kwargs: Any) -> Any:
        from vibecomfy.executor.agent_research_stage import (
            AgentResearchIteration,
            AgentResearchTrace,
        )
        from vibecomfy.executor.contracts import (
            ClassifyDecision,
            ExecutorResult,
            Report,
        )
        from vibecomfy.executor.core import AgentResearchResult
        from vibecomfy.executor.evidence_pack import (
            EvidenceArtifact,
            EvidenceLedger,
            EvidenceLedgerEntry,
            EvidencePack,
        )

        evidence_id = "harness:evidence:1"
        summary = (
            "Research found a distilled model path plus lightning/LCM "
            "sampler settings as the safest speed-focused options."
        )
        research = AgentResearchResult(
            route="research",
            trace=AgentResearchTrace(
                route="research",
                question="Find faster distilled variants for the video workflow.",
                iterations=(
                    AgentResearchIteration(
                        iteration=1,
                        question="Find faster distilled variants for the video workflow.",
                        tool_calls=(),
                        synthesis={"summary": summary},
                        verdict="enough",
                    ),
                ),
                final_verdict="enough",
                summary=summary,
                citations=(evidence_id,),
                uncertainty="",
                status="ok",
                elapsed_seconds=0.0,
            ),
            evidence_pack=EvidencePack(
                artifacts={
                    evidence_id: EvidenceArtifact(
                        evidence_id=evidence_id,
                        kind="harness_research_result",
                        body={
                            "title": "Distilled video workflow precedent",
                            "url": "local://workflow-precedents/distilled-video",
                        },
                        source="harness",
                    ),
                },
                ledger=EvidenceLedger(
                    entries=(
                        EvidenceLedgerEntry(
                            decision="research question",
                            conclusion=summary,
                            evidence_ids=(evidence_id,),
                            uncertainty="",
                        ),
                    )
                ),
            ),
            decision_memo={
                "question": "Find faster distilled variants for the video workflow.",
                "conclusion": summary,
                "citations": [evidence_id],
                "uncertainty": "",
                "next_action": "Use this conclusion for the requested next step.",
            },
        )

        return ExecutorResult.success(
            report=Report(
                plan=ClassifyDecision(
                    route="research",
                    task="research_nodes",
                    intent="research",
                    effort="medium",
                    plan_summary=(
                        "Research distilled, lightning, LCM, and lower-step "
                        "video workflow options before answering."
                    ),
                    research_goal="Find faster distilled variants for the video workflow.",
                    search_directions=(
                        "distilled video model variants",
                        "lightning or LCM sampler settings",
                        "step count and frame count tradeoffs",
                    ),
                    source_preferences=("workflow precedents", "node documentation"),
                    model_families=("distilled", "lightning", "LCM"),
                    pattern_category="speed_optimization",
                ),
                research=research,
            ),
            graph={"1": {"class_type": "KSampler", "inputs": {"steps": 8}}},
            reply=(
                "Use a distilled checkpoint or LoRA with lightning/LCM sampling, "
                "then reduce steps before lowering frame count."
            ),
        )

    monkeypatch.setattr(_fresh_executor_core(), "run_executor", fake_run_executor)


def _patch_ready_graph_explanation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")

    from vibecomfy.agent import service as svc

    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: {
            "ready": True,
            "route": "openrouter",
            "model": "live-contract-model",
        },
    )

    def fake_run_executor(*args: Any, **kwargs: Any) -> Any:
        from vibecomfy.executor.contracts import (
            ClassifyDecision,
            ExecutorResult,
            Report,
        )

        request = kwargs.get("request") or (args[0] if args else None)
        graph = getattr(request, "graph", None) if request is not None else None
        assert isinstance(graph, dict)
        assert {node["class_type"] for node in graph.values()} == {
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "KSampler",
        }

        return ExecutorResult.success(
            report=Report(
                plan=ClassifyDecision(
                    route="inspect",
                    task="inspect_graph",
                    intent="explain_graph",
                    effort="low",
                    plan_summary=(
                        "The graph is complete enough to inspect, so no "
                        "clarifying question is required before responding."
                    ),
                    known_graph_context=(
                        "CheckpointLoaderSimple feeds CLIPTextEncode and KSampler."
                    ),
                ),
            ),
            graph=graph,
            reply=(
                "No clarification is needed. This workflow loads an SD 1.5 "
                "checkpoint, encodes a positive prompt, and sends it to a "
                "KSampler for image generation."
            ),
        )

    monkeypatch.setattr(_fresh_executor_core(), "run_executor", fake_run_executor)


def test_headless_harness_runner_summarizes_blocked_prerequisite_without_executor_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_not_ready(monkeypatch)
    _patch_runner_in_process(monkeypatch)
    sys.modules.pop("vibecomfy.executor.core", None)

    from tests.live_agentic_harness.runner import run_tag

    scenarios_dir = tmp_path / "scenarios"
    _write_scenario(
        scenarios_dir,
        {
            "id": "missing-readiness",
            "query": "Update this workflow through the live harness.",
        },
    )

    summary = run_tag(
        "blocked-run",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
    )

    assert summary["tag"] == "blocked-run"
    assert summary["scenario_count"] == 1
    assert summary["overall_success"] is False
    assert json.loads(json.dumps(summary))["scenarios"][0]["scenario_id"] == "missing-readiness"

    [scenario_summary] = summary["scenarios"]
    assert scenario_summary["status"] == "blocked_prerequisite"
    assert scenario_summary["ok"] is False
    assert scenario_summary["readiness"]["ready"] is False
    assert scenario_summary["error"] == "missing live credentials"
    # The guard verdict now carries richer fields (metadata_success,
    # assessment, score_class); assert the contract-relevant subset.
    guard = scenario_summary["guard"]
    assert guard["output_dir"] == scenario_summary["output_dir"]
    assert guard["flow_kind"] == "live_agentic_headless"
    assert guard["status"] == "blocked_prerequisite"
    assert guard["dispatcher"] == "real"
    assert guard["model_behavior"] == "agentic"
    assert guard["live_agentic_success"] is False

    output_dir = Path(scenario_summary["output_dir"])
    assert (output_dir / "flow_metadata.json").is_file()
    flow_metadata = json.loads((output_dir / "flow_metadata.json").read_text(encoding="utf-8"))
    assert flow_metadata["status"] == "blocked_prerequisite"
    assert flow_metadata["readiness"]["reason"] == "missing live credentials"
    assert "vibecomfy.executor.core" not in sys.modules


def test_headless_harness_runner_json_mode_reports_blocked_prerequisite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_not_ready(monkeypatch)
    _patch_runner_in_process(monkeypatch)

    from tests.live_agentic_harness import runner

    scenarios_dir = tmp_path / "scenarios"
    _write_scenario(
        scenarios_dir,
        {
            "id": "blocked-json",
            "query": "Exercise JSON reporting for a blocked live run.",
        },
    )

    exit_code = runner.main(
        [
            "--tag",
            "json-run",
            "--scenarios-dir",
            str(scenarios_dir),
            "--output-base",
            str(tmp_path / "out"),
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_success"] is False
    assert payload["scenarios"][0]["status"] == "blocked_prerequisite"
    assert payload["scenarios"][0]["guard"]["live_agentic_success"] is False


def test_speed_distillation_scenario_blocks_cleanly_without_readiness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_not_ready(monkeypatch)
    _patch_runner_in_process(monkeypatch)

    from tests.live_agentic_harness.runner import run_tag

    scenarios_dir = tmp_path / "scenarios"
    _write_scenario(scenarios_dir, _SPEED_DISTILLATION_SCENARIO)

    summary = run_tag(
        "speed-blocked",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
    )

    [scenario_summary] = summary["scenarios"]
    assert summary["overall_success"] is False
    assert scenario_summary["scenario_id"] == "speed-distillation-research"
    assert scenario_summary["status"] == "blocked_prerequisite"
    assert scenario_summary["readiness"]["ready"] is False
    assert scenario_summary["guard"]["status"] == "blocked_prerequisite"
    assert scenario_summary["guard"]["dispatcher"] == "real"
    assert scenario_summary["guard"]["model_behavior"] == "agentic"
    assert scenario_summary["guard"]["live_agentic_success"] is False


def test_speed_distillation_scenario_records_live_research_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_ready_speed_research(monkeypatch)
    _patch_runner_in_process(monkeypatch)

    # Keep durable session artifacts inside the test tmp dir.
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.executor_durable.DEFAULT_SESSION_ROOT",
        tmp_path / "sessions",
    )

    from tests.live_agentic_harness.runner import run_tag

    scenarios_dir = tmp_path / "scenarios"
    _write_scenario(scenarios_dir, _SPEED_DISTILLATION_SCENARIO)

    summary = run_tag(
        "speed-live",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
    )

    [scenario_summary] = summary["scenarios"]
    output_dir = Path(scenario_summary["output_dir"])
    classification = json.loads((output_dir / "classification.json").read_text(encoding="utf-8"))
    research = json.loads((output_dir / "research.json").read_text(encoding="utf-8"))
    response = json.loads((output_dir / "response.json").read_text(encoding="utf-8"))
    flow_metadata = json.loads((output_dir / "flow_metadata.json").read_text(encoding="utf-8"))

    assert summary["overall_success"] is True
    assert scenario_summary["status"] == "success"
    assert scenario_summary["ok"] is True
    assert scenario_summary["guard"]["live_agentic_success"] is True
    assert classification["route"] == "research"
    assert classification["task"] == "research_nodes"
    assert classification["research"] is True
    assert classification["implement"] is False
    assert "distilled" in " ".join(classification["search_directions"]).lower()
    assert "lightning" in " ".join(classification["search_directions"]).lower()
    assert "distilled" in research["summary"].lower()
    assert "speed" in research["summary"].lower()
    assert response["ok"] is True
    assert "distilled" in response["reply"].lower()
    assert flow_metadata["flow_kind"] == "live_agentic_headless"
    assert flow_metadata["live"] is True
    assert flow_metadata["dispatcher"] == "real"
    assert flow_metadata["model_behavior"] == "agentic"


def test_live_graph_explanation_scenario_uses_headless_inspect_respond_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_ready_graph_explanation(monkeypatch)
    _patch_runner_in_process(monkeypatch)
    for module_name in (
        "aiohttp",
        "server",
        "vibecomfy.comfy_nodes.agent.routes",
        "vibecomfy.runtime.server",
        "vibecomfy.comfy_nodes.web",
    ):
        sys.modules.pop(module_name, None)

    # Keep durable session artifacts inside the test tmp dir.
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.executor_durable.DEFAULT_SESSION_ROOT",
        tmp_path / "sessions",
    )

    from tests.live_agentic_harness.runner import run_tag

    scenarios_dir = tmp_path / "scenarios"
    _write_scenario(scenarios_dir, _GRAPH_EXPLANATION_SCENARIO)

    summary = run_tag(
        "graph-live",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
    )

    [scenario_summary] = summary["scenarios"]
    output_dir = Path(scenario_summary["output_dir"])
    classification = json.loads((output_dir / "classification.json").read_text(encoding="utf-8"))
    response = json.loads((output_dir / "response.json").read_text(encoding="utf-8"))
    flow_metadata = json.loads((output_dir / "flow_metadata.json").read_text(encoding="utf-8"))
    request = json.loads((output_dir / "request.json").read_text(encoding="utf-8"))

    assert summary["overall_success"] is True
    assert scenario_summary["scenario_id"] == "live-graph-explanation-smoke"
    assert scenario_summary["status"] == "success"
    assert scenario_summary["guard"]["live_agentic_success"] is True
    assert classification["route"] == "inspect"
    assert classification["task"] == "inspect_graph"
    assert classification["reply"] is True
    assert classification["research"] is False
    assert classification["implement"] is False
    assert "clarifying question" in classification["plan_summary"]
    assert response["ok"] is True
    assert response["route"] == "inspect"
    assert response["outcome"]["kind"] == "noop"
    assert "clarification_required" not in response
    assert "No clarification is needed" in response["reply"]
    assert request["graph"]["3"]["class_type"] == "KSampler"
    assert flow_metadata["flow_kind"] == "live_agentic_headless"
    assert flow_metadata["entrypoint"] == "live_agentic_harness"
    assert flow_metadata["frontend"] == "not_used"
    assert flow_metadata["live"] is True
    assert flow_metadata["dispatcher"] == "real"
    assert flow_metadata["model_behavior"] == "agentic"
    assert not (output_dir / "research.json").exists()
    assert not (output_dir / "implementation_payload.json").exists()
    assert "aiohttp" not in sys.modules
    assert "server" not in sys.modules
    assert "vibecomfy.comfy_nodes.agent.routes" not in sys.modules
    assert "vibecomfy.runtime.server" not in sys.modules
    assert "vibecomfy.comfy_nodes.web" not in sys.modules


def test_live_graph_explanation_scenario_and_brief_are_headless_smoke_contract() -> None:
    scenario_path = (
        Path(__file__).resolve().parent
        / "live_agentic_harness"
        / "scenarios"
        / "live-graph-explanation-smoke.json"
    )
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))

    brief_path = scenario_path.parents[1] / scenario["brief"]
    brief = brief_path.read_text(encoding="utf-8")
    normalized_brief = " ".join(brief.split())

    assert scenario["id"] == "live-graph-explanation-smoke"
    assert "clarifying question" in scenario["query"]
    assert "inspect the workflow" in scenario["query"]
    assert "answer directly" in scenario["query"]
    assert {node["class_type"] for node in scenario["graph"].values()} == {
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "KSampler",
    }
    assert "live headless agent path" in normalized_brief
    assert "not the ComfyUI browser panel" in normalized_brief
    assert "not a running ComfyUI server" in normalized_brief
    assert "blocked_prerequisite" in brief
    assert "inspect/explain graph" in brief
    assert "Do not ask a clarifying question" in brief
    assert "non-empty explanation" in brief
    assert "flow_kind=live_agentic_headless" in brief
    assert "dispatcher=real" in brief
    assert "model_behavior=agentic" in brief
