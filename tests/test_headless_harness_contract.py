"""HEADLESS HARNESS CONTRACT TESTS.

Headless harness contract tests that exercise the real executor pipeline.

These tests run the same ``classify → research → implement → reply`` path the
ComfyUI app route uses, but with deterministic fake model backends and no
network.  They prove that the headless harness wires all the way through the
internal workflow, not just the headless service shell.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Generator

import pytest

from tests.live_agentic_harness.guard import guard_output_dir
from vibecomfy.agent.contracts import HeadlessAgentRequest
from vibecomfy.executor.contracts import ClassifyDecision
from vibecomfy.executor.profiles import set_profile_override_dir


class _LegacyResearchResult:
    """Duck-typed stand-in for the deleted legacy ``ResearchResult`` contract.

    The class was removed by the agent-judgment rework (D02); the shadow /
    dual-evaluation seam consumes this shape via ``getattr`` only.
    """

    def __init__(self, summary: str = "", sources: tuple = (), warnings: tuple = (), community_summary: str = "") -> None:
        self.summary = summary
        self.sources = sources
        self.warnings = warnings
        self.community_summary = community_summary


_BASE_PROFILE = """
[classify]
agent = "hermes"
model = "deepseek-v4-flash"
effort = "low"

[research]
agent = "hermes"
model = "deepseek-v4-pro"
effort = "medium"

[implement]
agent = "codex"
model = "gpt-5.4"
effort = "high"

[reply]
agent = "hermes"
model = "deepseek-v4-pro"
effort = "low"
"""


def _write_toml(dir_path: Path, name: str, content: str) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{name}.toml"
    file_path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return file_path


@pytest.fixture
def profile_dir(tmp_path: Path) -> Generator[Path, None, None]:
    dir_path = tmp_path / "profiles"
    _write_toml(dir_path, "default", _BASE_PROFILE)
    set_profile_override_dir(dir_path)
    yield dir_path
    set_profile_override_dir(None)


def _set_headless_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")


def _patch_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.agent import service as svc

    monkeypatch.setattr(
        svc,
        "_check_live_readiness",
        lambda request: {
            "ready": True,
            "route": "openrouter",
            "model": "e2e-contract-model",
        },
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _patch_runner_in_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run harness scenarios in-process instead of in per-scenario subprocesses.

    The harness runner fans out to isolated ``--single`` subprocesses by
    default, which would shield the executor from the deterministic fakes
    these tests install.  The fake subprocess delegates to the runner's own
    in-process ``run_single`` entry point — the exact code path a subprocess
    would execute — so the real headless pipeline still runs, with the
    monkeypatched readiness/executor seams applied.
    """

    def fake_subprocess_run(
        cmd: list[str], **kwargs: Any
    ) -> tuple[int, str, str]:
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
        return (0, "", "")

    monkeypatch.setattr(
        "tests.live_agentic_harness.runner._run_scenario_subprocess",
        fake_subprocess_run,
    )


def _minimal_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 1,
                "class_type": "CheckpointLoaderSimple",
                "inputs": [],
                "outputs": [{"name": "MODEL"}, {"name": "CLIP"}, {"name": "VAE"}],
            },
            {
                "id": 2,
                "class_type": "CLIPTextEncode",
                "inputs": [{"name": "clip", "link": 1}],
                "outputs": [{"name": "CONDITIONING"}],
            },
            {
                "id": 3,
                "class_type": "KSampler",
                "inputs": [
                    {"name": "model", "link": 2},
                    {"name": "positive", "link": 3},
                ],
                "outputs": [{"name": "LATENT"}],
            },
        ],
        "links": [
            [1, 1, 1, 2, 0, "CLIP"],
            [2, 1, 0, 3, 0, "MODEL"],
            [3, 2, 0, 3, 1, "CONDITIONING"],
        ],
    }


def test_headless_inspect_route_runs_full_executor_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile_dir: Path,
) -> None:
    """The headless service runs classify + reply through the real executor core."""
    _set_headless_env(monkeypatch)
    _patch_readiness(monkeypatch)

    from vibecomfy.agent import service as svc
    from vibecomfy.executor import core as executor_core

    classify_called: list[dict[str, Any]] = []
    reply_called: list[dict[str, Any]] = []

    def fake_classify(query: str, **kwargs: Any) -> ClassifyDecision:
        classify_called.append({"query": query, "kwargs": kwargs})
        return ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            effort="low",
            plan_summary="Explain the attached graph.",
            intent="explain_graph",
            route="inspect",
            task="inspect_graph",
        )

    def fake_reply(query: str, **kwargs: Any) -> str:
        reply_called.append({"query": query, "kwargs": kwargs})
        return "This graph loads a checkpoint, encodes a prompt, and samples a latent."

    monkeypatch.setattr(executor_core, "run_classify_turn", fake_classify)
    monkeypatch.setattr(executor_core, "run_reply_turn", fake_reply)

    # Keep durable session artifacts inside the test tmp dir.
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.executor_durable.DEFAULT_SESSION_ROOT",
        tmp_path / "sessions",
    )

    output_dir = tmp_path / "inspect-out"
    request = HeadlessAgentRequest(
        query="Explain this graph.",
        graph=_minimal_graph(),
        output_dir=output_dir,
        live=True,
        profile="default",
    )

    result = svc.run_headless(request, entrypoint="agentic_e2e")

    assert result.status == "success"
    assert result.ok is True
    assert classify_called
    assert reply_called

    classification = _read_json(output_dir / "classification.json")
    response = _read_json(output_dir / "response.json")
    flow_metadata = _read_json(output_dir / "flow_metadata.json")
    request_artifact = _read_json(output_dir / "request.json")

    assert classification["route"] == "inspect"
    assert classification["task"] == "inspect_graph"
    assert classification["research"] is False
    assert classification["implement"] is False
    assert response["ok"] is True
    assert response["route"] == "inspect"
    assert response["outcome"]["kind"] == "noop"
    assert "graph loads a checkpoint" in response["reply"]
    assert flow_metadata["flow_kind"] == "live_agentic_headless"
    assert flow_metadata["entrypoint"] == "agentic_e2e"
    assert flow_metadata["dispatcher"] == "real"
    assert flow_metadata["model_behavior"] == "agentic"
    assert flow_metadata["live"] is True
    assert flow_metadata["status"] == "success"
    assert request_artifact["query"] == "Explain this graph."
    assert not (output_dir / "research.json").exists()
    assert not (output_dir / "implementation_payload.json").exists()
    assert not (output_dir / "implementation_result.json").exists()

    guard = guard_output_dir(output_dir)
    assert guard["live_agentic_success"] is True
    assert guard["dispatcher"] == "real"
    assert guard["model_behavior"] == "agentic"


def test_headless_research_route_runs_full_executor_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile_dir: Path,
) -> None:
    """The research route runs deterministic research + semantic reply (PR-B).

    The headless service wires classify → deterministic research → reply
    through the real executor core.  The agent-edit batch gate never runs.
    """
    _set_headless_env(monkeypatch)
    _patch_readiness(monkeypatch)

    from vibecomfy.agent import service as svc
    from vibecomfy.executor import core as executor_core

    classify_called: list[dict[str, Any]] = []
    research_called: list[dict[str, Any]] = []
    edit_called: list[dict[str, Any]] = []

    def fake_classify(query: str, **kwargs: Any) -> ClassifyDecision:
        classify_called.append({"query": query, "kwargs": kwargs})
        return ClassifyDecision(
            research=True,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="Research faster video options.",
            intent="research",
            route="research",
            task="research_nodes",
            research_goal="Find distilled or faster ways to run the current video workflow.",
            search_directions=("distilled video models", "lightning/LCM samplers"),
            source_preferences=("workflows", "node documentation"),
            avoid=("generic web search",),
            known_graph_context="Video workflow attached.",
        )

    def fake_research(query: str, **kwargs: Any) -> _LegacyResearchResult:
        research_called.append({"query": query, "kwargs": kwargs})
        return _LegacyResearchResult(
            summary="Research found distilled checkpoints and Lightning/LCM samplers.",
            sources=(),
            warnings=(),
        )

    def fake_reply(query: str, **kwargs: Any) -> str:
        return "Research found distilled checkpoints and Lightning/LCM samplers."

    def fake_handle_agent_edit(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        edit_called.append({"payload": payload, "kwargs": kwargs})
        raise AssertionError("research route must never reach the agent-edit gate")

    from vibecomfy.executor.agent_research_stage import AgentResearchTrace
    from vibecomfy.executor.core import AgentResearchResult
    from vibecomfy.executor.evidence_pack import EvidenceLedger, EvidencePack

    def fake_agent_research(request: Any, spec: Any, *, plan: Any) -> AgentResearchResult:
        research_called.append({"request": request, "spec": spec, "plan": plan})
        trace = AgentResearchTrace(
            route="research",
            question="Is there a faster way to run this video workflow?",
            iterations=(),
            final_verdict="enough",
            summary="Research found distilled checkpoints and Lightning/LCM samplers.",
            citations=(),
            uncertainty="",
            status="ok",
            elapsed_seconds=0.01,
            warnings=(),
        )
        return AgentResearchResult(
            route="research",
            trace=trace,
            evidence_pack=EvidencePack(artifacts={}, ledger=EvidenceLedger(entries=())),
            decision_memo={
                "question": "Is there a faster way to run this video workflow?",
                "conclusion": "Research found distilled checkpoints and Lightning/LCM samplers.",
                "citations": [],
                "uncertainty": "",
                "next_action": "Use this conclusion for the requested next step.",
            },
        )

    monkeypatch.setattr(executor_core, "run_classify_turn", fake_classify)
    monkeypatch.setattr(executor_core, "_run_agent_owned_research", fake_agent_research)
    monkeypatch.setattr(executor_core, "run_reply_turn", fake_reply)
    monkeypatch.setattr(executor_core, "handle_agent_edit", fake_handle_agent_edit)

    output_dir = tmp_path / "research-out"
    request = HeadlessAgentRequest(
        query="Is there a faster way to run this video workflow?",
        graph=_minimal_graph(),
        output_dir=output_dir,
        live=True,
        profile="default",
    )

    result = svc.run_headless(request, entrypoint="agentic_e2e")

    assert result.status == "success"
    assert result.ok is True
    assert classify_called
    assert not edit_called
    # C01: research is agent-owned — the C1 stage runs once with the research
    # route; the legacy deterministic engine is never invoked.
    assert len(research_called) == 1
    assert research_called[0]["plan"].effective_route == "research"

    classification = _read_json(output_dir / "classification.json")
    research_artifact = _read_json(output_dir / "research.json")
    response = _read_json(output_dir / "response.json")
    flow_metadata = _read_json(output_dir / "flow_metadata.json")

    assert classification["route"] == "research"
    assert classification["task"] == "research_nodes"
    assert classification["research"] is True
    assert classification["implement"] is False
    assert research_artifact["mode"] == "agent_owned"
    assert research_artifact["conclusion"].startswith(
        "Research found distilled checkpoints and Lightning/LCM samplers."
    )
    assert response["ok"] is True
    assert response["route"] == "research"
    assert "distilled" in response["reply"].lower() or "lightning" in response["reply"].lower()
    assert flow_metadata["status"] == "success"
    assert flow_metadata["dispatcher"] == "real"
    assert flow_metadata["model_behavior"] == "agentic"

    guard = guard_output_dir(output_dir)
    assert guard["live_agentic_success"] is True


def test_headless_harness_runner_dispatches_through_real_executor_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile_dir: Path,
) -> None:
    """The harness runner discovers a scenario and runs the full executor pipeline."""
    _set_headless_env(monkeypatch)
    _patch_readiness(monkeypatch)
    _patch_runner_in_process(monkeypatch)

    from tests.live_agentic_harness.runner import run_tag
    from vibecomfy.executor import core as executor_core

    def fake_classify(query: str, **kwargs: Any) -> ClassifyDecision:
        return ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            effort="low",
            plan_summary="Explain the attached graph.",
            intent="explain_graph",
            route="inspect",
            task="inspect_graph",
        )

    def fake_reply(query: str, **kwargs: Any) -> str:
        return "This is a text-to-image workflow."

    monkeypatch.setattr(executor_core, "run_classify_turn", fake_classify)
    monkeypatch.setattr(executor_core, "run_reply_turn", fake_reply)

    # Keep durable session artifacts inside the test tmp dir.
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.executor_durable.DEFAULT_SESSION_ROOT",
        tmp_path / "sessions",
    )

    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = scenarios_dir / "inspect-graph-e2e.json"
    scenario_path.write_text(
        json.dumps(
            {
                "id": "inspect-graph-e2e",
                "query": "Explain this graph using the real executor pipeline.",
                "graph": _minimal_graph(),
            }
        ),
        encoding="utf-8",
    )

    from tests.live_agentic_harness.scenario_manifest import build_manifest

    (tmp_path / "scenario_manifest.json").write_text(
        json.dumps(build_manifest(scenarios_dir)),
        encoding="utf-8",
    )

    summary = run_tag(
        "e2e-run",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
    )

    assert summary["tag"] == "e2e-run"
    assert summary["overall_success"] is True
    assert summary["scenario_count"] == 1

    scenario_summary = summary["scenarios"][0]
    assert scenario_summary["scenario_id"] == "inspect-graph-e2e"
    assert scenario_summary["status"] == "success"
    assert scenario_summary["ok"] is True
    assert scenario_summary["guard"]["live_agentic_success"] is True

    output_dir = Path(scenario_summary["output_dir"])
    response = _read_json(output_dir / "response.json")
    assert response["ok"] is True
    assert response["route"] == "inspect"
    assert "text-to-image workflow" in response["reply"]
