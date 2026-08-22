from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("staged", "staged"),
        ("threaded", "threaded"),
        ("full", "staged"),
        ("two_step", "threaded"),
    ],
)
def test_headless_mode_boundary_canonicalizes_aliases(raw: str, canonical: str) -> None:
    from vibecomfy.agent.contracts import HeadlessAgentRequest

    request = HeadlessAgentRequest.from_payload({"query": "edit", "pipeline_mode": raw})

    assert request.pipeline_mode == canonical
    assert request.to_dict()["pipeline_mode"] == canonical
    assert request.to_executor_request().pipeline_mode == canonical


def test_headless_default_preserves_staged_compatibility_omission() -> None:
    from vibecomfy.agent.contracts import HeadlessAgentRequest

    request = HeadlessAgentRequest(query="edit")

    assert request.pipeline_mode is None
    assert "pipeline_mode" not in request.to_dict()
    assert request.to_executor_request().pipeline_mode is None


def test_headless_cli_exposes_mode_and_accepts_legacy_alias() -> None:
    from vibecomfy.agent.__main__ import _build_parser

    args = _build_parser().parse_args(["edit", "--mode", "two_step"])

    assert args.pipeline_mode == "two_step"


def test_threaded_readiness_uses_execute_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy.agent import service
    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.comfy_nodes.agent import provider

    stages: list[str] = []
    request = HeadlessAgentRequest(query="edit", pipeline_mode="threaded")

    def readiness_kwargs(*, stage: str = "classify") -> dict[str, str | None]:
        stages.append(stage)
        return {"route": "opensource", "model": "execute-model"}

    object.__setattr__(request, "resolve_provider_readiness_kwargs", readiness_kwargs)
    monkeypatch.setattr(
        provider,
        "readiness",
        lambda **kwargs: {"ready": True, **kwargs},
    )

    result = service._check_live_readiness(request)

    assert stages == ["execute"]
    assert result["route"] == "opensource"
    assert result["model"] == "execute-model"


def test_environment_threaded_readiness_uses_execute_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    monkeypatch.setenv("VIBECOMFY_EXECUTOR_PIPELINE_MODE", "two_step")
    from vibecomfy.agent import service
    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.comfy_nodes.agent import provider

    stages: list[str] = []
    request = HeadlessAgentRequest(query="edit")

    def readiness_kwargs(*, stage: str = "classify") -> dict[str, str | None]:
        stages.append(stage)
        return {"route": "opensource", "model": "execute-model"}

    object.__setattr__(request, "resolve_provider_readiness_kwargs", readiness_kwargs)
    monkeypatch.setattr(
        provider,
        "readiness",
        lambda **kwargs: {"ready": True, **kwargs},
    )

    result = service._check_live_readiness(request)

    assert stages == ["execute"]
    assert result["route"] == "opensource"
    assert result["model"] == "execute-model"


def test_environment_threaded_mode_is_materialized_before_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor import threaded
    from vibecomfy.executor.contracts import ExecutorRequest
    from vibecomfy.executor.core import run_executor

    captured: dict[str, object] = {}
    sentinel = object()

    def fake_threaded(request: ExecutorRequest, **kwargs: object) -> object:
        captured["request"] = request
        return sentinel

    monkeypatch.setenv("VIBECOMFY_EXECUTOR_PIPELINE_MODE", "two_step")
    monkeypatch.setattr(threaded, "run_threaded_executor", fake_threaded)
    ports = SimpleNamespace(classify_failure=lambda *args, **kwargs: None)

    result = run_executor(ExecutorRequest(query="edit"), host_ports=ports)

    assert result is sentinel
    request = captured["request"]
    assert isinstance(request, ExecutorRequest)
    assert request.pipeline_mode == "threaded"


def test_chat_recovery_returns_latest_canonical_mode(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent._frag_chat import read_session_chat
    from vibecomfy.comfy_nodes.agent.contracts import public_chat_rehydrate_payload

    session_id = "mode-session"
    for turn_id, mode in [("0000", "full"), ("0001", "two_step"), ("0002", None)]:
        turn_dir = tmp_path / session_id / "turns" / turn_id
        turn_dir.mkdir(parents=True)
        request = {"task": "edit"}
        if mode is not None:
            request["pipeline_mode"] = mode
        (turn_dir / "request.json").write_text(
            json.dumps(request),
            encoding="utf-8",
        )
        (turn_dir / "response.json").write_text(
            json.dumps({"ok": True, "message": "done", "graph_unchanged": True}),
            encoding="utf-8",
        )

    raw = read_session_chat(tmp_path, session_id)
    public = public_chat_rehydrate_payload(raw)

    assert raw["pipeline_mode"] == "staged"
    assert public["pipeline_mode"] == "staged"


def test_chat_recovery_ignores_partial_newer_turn_mode(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent._frag_chat import read_session_chat

    session_id = "partial-mode-session"
    complete_turn = tmp_path / session_id / "turns" / "0000"
    complete_turn.mkdir(parents=True)
    (complete_turn / "request.json").write_text(
        json.dumps({"task": "edit", "pipeline_mode": "threaded"}),
        encoding="utf-8",
    )
    (complete_turn / "response.json").write_text(
        json.dumps({"ok": True, "message": "done", "graph_unchanged": True}),
        encoding="utf-8",
    )

    # Allocation may persist request.json before the response/chat artifacts
    # are closed. This incomplete turn must not change recovery mode.
    partial_turn = tmp_path / session_id / "turns" / "0001"
    partial_turn.mkdir(parents=True)
    (partial_turn / "request.json").write_text(
        json.dumps({"task": "edit"}),
        encoding="utf-8",
    )

    raw = read_session_chat(tmp_path, session_id)

    assert raw["latest_turn_id"] == "0000"
    assert raw["pipeline_mode"] == "threaded"


def test_executor_only_durable_request_persists_canonical_mode(tmp_path: Path) -> None:
    from vibecomfy.comfy_nodes.agent.executor_durable import (
        maybe_write_executor_only_durable_turn,
    )
    from vibecomfy.executor.contracts import ExecutorRequest

    request = ExecutorRequest(
        query="explain",
        pipeline_mode="two_step",
        session_id="durable-mode",
    )
    result = SimpleNamespace()
    response = maybe_write_executor_only_durable_turn(
        response={"ok": True, "route": "respond", "message": "done"},
        result=result,
        payload=request.to_dict(),
        request=request,
        session_root=tmp_path,
    )

    request_path = (
        tmp_path / response["session_id"] / "turns" / response["turn_id"] / "request.json"
    )
    persisted = json.loads(request_path.read_text(encoding="utf-8"))
    assert persisted["pipeline_mode"] == "threaded"


# ── T4.2: staged adapter wire compatibility through both carriers ────────────


def _t42_staged_report():
    from vibecomfy.executor.agent_research_stage import AgentResearchTrace
    from vibecomfy.executor.contracts import ClassifyDecision, Report
    from vibecomfy.executor.core import AgentResearchResult
    from vibecomfy.executor.evidence_pack import (
        EvidenceArtifact,
        EvidenceLedger,
        EvidenceLedgerEntry,
        EvidencePack,
    )

    trace = AgentResearchTrace(
        route="research",
        question="q",
        iterations=(),
        final_verdict="enough",
        summary="s",
        citations=(),
        uncertainty="",
        status="ok",
        elapsed_seconds=0.0,
        budget={"deadline_seconds": 450.0, "turns_used": 0, "deadline_reached": False},
    )
    pack = EvidencePack(
        artifacts={
            "hivemind_get:fixture": EvidenceArtifact(
                evidence_id="hivemind_get:fixture",
                kind="hivemind_get",
                body={"content": "fixture"},
            ),
        },
        ledger=EvidenceLedger(
            entries=(
                EvidenceLedgerEntry(
                    decision="hivemind_get",
                    conclusion="fetched",
                    evidence_ids=("hivemind_get:fixture",),
                    uncertainty="",
                    tool_status="ok",
                ),
            )
        ),
    )
    return Report(
        plan=ClassifyDecision(route="research", task="research_nodes"),
        research=AgentResearchResult(
            route="research", trace=trace, evidence_pack=pack
        ),
    )


def test_t42_staged_report_omits_orchestration_mode_and_keeps_envelope_stable():
    from dataclasses import replace

    from vibecomfy.executor.contracts import (
        RESEARCH_EVIDENCE_SHARED_KEYS,
        Report,
    )

    staged = _t42_staged_report().to_dict()["executor"]
    # Staged omission is byte-compatible: no orchestration_mode key anywhere.
    assert "orchestration_mode" not in staged
    # The T4.1 shared evidence fields ride INSIDE the research payload
    # additively; the envelope keys themselves are unchanged.
    assert RESEARCH_EVIDENCE_SHARED_KEYS <= set(staged["research"])

    threaded = replace(
        _t42_staged_report(), orchestration_mode="threaded"
    ).to_dict()["executor"]
    assert threaded["orchestration_mode"] == "threaded"


def test_t42_staged_serialization_round_trips_through_both_carriers():
    from vibecomfy.comfy_nodes.agent.executor_response import serialize_executor_result
    from vibecomfy.executor.contracts import ExecutorResult

    result = ExecutorResult.success(report=_t42_staged_report(), reply="memo")
    serialized = serialize_executor_result(result)
    assert "orchestration_mode" not in serialized
    research = serialized["report"]["executor"]["research"]
    assert research["mode"] == "agent_owned"
    assert research["budget"]["deadline_seconds"] == 450.0


def test_t42_research_phase_deadline_default_is_one_shared_constant():
    from vibecomfy.executor.agent_research_stage import TOOL_PHASE_DEADLINE_SECONDS
    from vibecomfy.executor.tool_contracts import RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS

    # ONE canonical default: the staged stage constant and the shared knob
    # fallback agree, and both readers (executor.core, edit_batch_repl) read
    # this single name.
    assert RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS == 450.0
    assert TOOL_PHASE_DEADLINE_SECONDS == RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS
