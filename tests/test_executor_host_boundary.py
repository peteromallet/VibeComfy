from __future__ import annotations

import subprocess
import sys
from typing import Any

from vibecomfy.executor import core as executor_core
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorHostPorts,
    ExecutorRequest,
)
from vibecomfy.executor.profiles import AgentSpecShape


def test_importing_executor_core_does_not_load_comfy_agent_internals() -> None:
    code = """
import sys
import vibecomfy.executor.core

for name in (
    "vibecomfy.comfy_nodes.agent.contracts",
    "vibecomfy.comfy_nodes.agent.edit",
    "vibecomfy.comfy_nodes.agent.provider",
    "vibecomfy.comfy_nodes.agent.runtime",
    "vibecomfy.comfy_nodes.agent.executor_adapter",
):
    assert name not in sys.modules, name
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_implement_phase_accepts_injected_host_ports(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_edit(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {
            "ok": True,
            "message": "Candidate ready.",
            "graph": {"nodes": [{"id": 2, "type": "SaveImage"}], "links": []},
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "apply_eligibility": {"applyable": True},
        }

    def unexpected(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"unexpected host operation: {args!r} {kwargs!r}")

    ports = ExecutorHostPorts(
        handle_agent_edit=fake_edit,
        payload_hash=lambda payload: "injected-request-hash",
        classify_failure=unexpected,
        failure_envelope=unexpected,
        begin_deepseek_usage_capture=unexpected,
        snapshot_deepseek_usage_capture=unexpected,
        end_deepseek_usage_capture=unexpected,
        begin_model_attempt_capture=unexpected,
        snapshot_model_attempt_capture=unexpected,
        end_model_attempt_capture=unexpected,
    )
    monkeypatch.setattr(
        executor_core,
        "_default_host_ports",
        lambda: unexpected("default adapter must stay unused"),
    )

    result = executor_core._run_implement(
        ExecutorRequest(
            query="add an image saver",
            graph={"nodes": [{"id": 1, "type": "VAEDecode"}], "links": []},
        ),
        AgentSpecShape(agent="codex", model="gpt-5.4", effort="high"),
        plan=ClassifyDecision(
            route="revise",
            implement=True,
            intent="edit",
            task="edit_graph",
        ),
        host_ports=ports,
    )

    assert result.graph == {"nodes": [{"id": 2, "type": "SaveImage"}], "links": []}
    assert captured["kwargs"]["idempotency_request_hash"] == "injected-request-hash"
    assert captured["payload"]["executor_route"] == "revise"
