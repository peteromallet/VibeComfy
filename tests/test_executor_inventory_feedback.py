"""Typed implement -> research inventory feedback regressions (no live calls)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from vibecomfy.executor import core
from vibecomfy.executor.agent_research_stage import (
    MAX_RESEARCH_TOOL_CALLS,
    AgentResearchTrace,
    run_agent_research_stage,
)
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorHostPorts,
    ExecutorRequest,
    ImplementationResult,
)
from vibecomfy.executor.evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidencePack,
)
from vibecomfy.executor.stage_contracts import (
    ImplementMissingClassesFeedback,
    StagePackage,
)
from vibecomfy.executor.tool_contracts import ToolStatus


def _ports(*, handle_agent_edit=None) -> ExecutorHostPorts:
    def unused(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unused host operation")

    return ExecutorHostPorts(
        handle_agent_edit=handle_agent_edit or unused,
        payload_hash=lambda payload: "hash",
        classify_failure=unused,
        failure_envelope=unused,
        begin_deepseek_usage_capture=lambda: None,
        snapshot_deepseek_usage_capture=lambda: ({}, True),
        end_deepseek_usage_capture=lambda token: None,
        begin_model_attempt_capture=lambda: None,
        snapshot_model_attempt_capture=lambda: (),
        end_model_attempt_capture=lambda token: None,
    )


def _research_result(
    conclusion: str,
    *,
    turns_used: int,
    executed_tool_calls: int = 0,
    deadline_seconds: float = 90.0,
    elapsed_seconds: float = 10.0,
) -> core.AgentResearchResult:
    evidence_id = f"evidence:{conclusion}"
    artifact = EvidenceArtifact(
        evidence_id=evidence_id,
        kind="test",
        body={"conclusion": conclusion},
        source="test",
    )
    ledger = EvidenceLedger(
        entries=(
            EvidenceLedgerEntry(
                decision="synthesize",
                conclusion=conclusion,
                evidence_ids=(evidence_id,),
                uncertainty="",
            ),
        )
    )
    budget = {
        "deadline_seconds": deadline_seconds,
        "turns_used": turns_used,
        "deadline_reached": False,
        "tool_calls_used": executed_tool_calls,
        "tool_call_limit": MAX_RESEARCH_TOOL_CALLS,
        "tool_calls_remaining": max(
            0, MAX_RESEARCH_TOOL_CALLS - executed_tool_calls
        ),
    }
    trace = AgentResearchTrace(
        route="adapt",
        question="q",
        iterations=(),
        final_verdict="enough",
        summary=conclusion,
        citations=(evidence_id,),
        uncertainty="",
        status="ok",
        elapsed_seconds=elapsed_seconds,
        executed_tool_calls=executed_tool_calls,
        budget=budget,
    )
    pack = EvidencePack(artifacts={evidence_id: artifact}, ledger=ledger)
    return core.AgentResearchResult(
        route="adapt",
        trace=trace,
        evidence_pack=pack,
        package=StagePackage(
            stage_id="research",
            produced_at="2026-09-08T00:00:00Z",
            artifacts=pack.artifacts,
            diagnostics=(),
            status=ToolStatus.OK,
            next_stage_hints=("implement",),
            ledger=ledger,
            research_attempt="grounded",
            budget=budget,
        ),
    )


def _missing_result(
    *,
    outcome_class: str = "SaveAudio",
    receipt_class: str = "SaveAudio",
    question: str = "Which authorable class can save this output as FLAC?",
    outcome_kind: str = "requires_custom_nodes",
    explicit_feedback: bool = True,
) -> ImplementationResult:
    receipt = {
        "node_class": receipt_class,
        "status": "no_results",
        "source": "implement",
    }
    durable_response = {
        "ok": True,
        "message": question,
        "terminal_state": "no_candidate",
        "graph_unchanged": True,
        "no_candidate_reason": "no_changes",
        "debug": {"batch_repl": {"exit_mode": "pure_clarify"}},
        "internal_outcome": {"kind": "clarify", "question": question},
        "outcome": {
            "kind": outcome_kind,
            "question": question,
            "missing_classes": [outcome_class],
        },
        "batch_turns": [
            {
                "statements": [
                    {
                        "detail": {
                            "query": "search",
                            "missing_classes": [receipt_class],
                        }
                    }
                ]
            }
        ],
        "accepted_batch": [],
    }
    if explicit_feedback:
        durable_response["implement_missing_classes_feedback"] = {
            "question": question,
            "missing_classes": [outcome_class],
            "lookup_receipts": [receipt],
        }
    return ImplementationResult(
        message=question,
        durable_response=durable_response,
    )


def test_projected_missing_classes_without_explicit_contract_does_not_reenter_research(
    monkeypatch,
) -> None:
    research_calls = 0
    implement_calls = 0
    projected_only = _missing_result(explicit_feedback=False)

    assert core._implement_missing_classes_feedback(projected_only) is None

    monkeypatch.setattr(
        core,
        "_resolve_spec",
        lambda *args, **kwargs: SimpleNamespace(agent="test", model="test", effort="low"),
    )
    monkeypatch.setattr(
        core,
        "_run_classify",
        lambda *args, **kwargs: ClassifyDecision(
            intent="edit", route="revise", research=False, implement=True, reply=True
        ),
    )

    def fake_research(*args: Any, **kwargs: Any) -> core.AgentResearchResult:
        nonlocal research_calls
        research_calls += 1
        return _research_result("unexpected", turns_used=1)

    def fake_implement(*args: Any, **kwargs: Any) -> ImplementationResult:
        nonlocal implement_calls
        implement_calls += 1
        return projected_only

    monkeypatch.setattr(core, "_run_agent_owned_research", fake_research)
    monkeypatch.setattr(core, "_run_implement", fake_implement)
    monkeypatch.setattr(core, "_run_reply", lambda *args, **kwargs: "Need your choice.")

    result = core.run_executor(
        ExecutorRequest(
            query="Change SaveAudioMP3 to FLAC",
            graph={"nodes": [{"id": 1, "type": "SaveAudioMP3"}], "links": []},
        ),
        host_ports=_ports(),
    )

    assert result.ok is True
    assert implement_calls == 1
    assert research_calls == 0
    assert result.report.implementation.durable_response["outcome"]["kind"] == (
        "requires_custom_nodes"
    )


def test_agent_authored_missing_classes_question_reenters_research_once(
    monkeypatch,
) -> None:
    """The agent chooses the feedback edge; core only transports and bounds it."""
    research_calls: list[dict[str, Any]] = []
    implement_calls: list[dict[str, Any]] = []
    resumed = _research_result("Use ExactFlacSaver", turns_used=4)
    implementations = iter(
        (
            _missing_result(),
            ImplementationResult(
                graph={"nodes": [{"id": 1, "type": "ExactFlacSaver"}], "links": []},
                message="Replaced the saver.",
                durable_response={"ok": True, "outcome": {"kind": "candidate"}},
            ),
        )
    )

    monkeypatch.setattr(
        core,
        "_resolve_spec",
        lambda *args, **kwargs: SimpleNamespace(agent="test", model="test", effort="low"),
    )
    monkeypatch.setattr(
        core,
        "_run_classify",
        lambda *args, **kwargs: ClassifyDecision(
            intent="edit", route="revise", research=False, implement=True, reply=True
        ),
    )

    def fake_research(*args: Any, **kwargs: Any) -> core.AgentResearchResult:
        research_calls.append(kwargs)
        return resumed

    def fake_implement(*args: Any, **kwargs: Any) -> ImplementationResult:
        implement_calls.append(kwargs)
        return next(implementations)

    monkeypatch.setattr(core, "_run_agent_owned_research", fake_research)
    monkeypatch.setattr(core, "_run_implement", fake_implement)
    monkeypatch.setattr(core, "_run_reply", lambda *args, **kwargs: "done")

    result = core.run_executor(
        ExecutorRequest(
            query="Change SaveAudioMP3 to FLAC",
            graph={"nodes": [{"id": 1, "type": "SaveAudioMP3"}], "links": []},
        ),
        host_ports=_ports(),
    )

    assert result.ok is True
    assert len(research_calls) == 1
    feedback = research_calls[0]["implement_feedback"]
    assert isinstance(feedback, ImplementMissingClassesFeedback)
    assert feedback.question == "Which authorable class can save this output as FLAC?"
    assert feedback.missing_classes == ("SaveAudio",)
    assert research_calls[0]["prior_result"] is None
    assert len(implement_calls) == 2
    assert implement_calls[1]["inventory_feedback"] is feedback
    assert implement_calls[1]["research_result"] is resumed


def test_real_run_implement_preserves_explicit_feedback_contract() -> None:
    durable = _missing_result().durable_response
    seen_payload: dict[str, Any] = {}

    def handle_agent_edit(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        seen_payload.update(payload)
        return dict(durable)

    result = core._run_implement(
        ExecutorRequest(
            query="Change SaveAudioMP3 to FLAC",
            graph={"nodes": [{"id": 1, "type": "SaveAudioMP3"}], "links": []},
        ),
        SimpleNamespace(agent="test", model="test", effort="low"),
        plan=ClassifyDecision(
            intent="edit", route="revise", research=False, implement=True, reply=True
        ),
        host_ports=_ports(handle_agent_edit=handle_agent_edit),
    )

    feedback = core._implement_missing_classes_feedback(result)
    assert feedback is not None
    assert feedback.question == "Which authorable class can save this output as FLAC?"
    assert feedback.missing_classes == ("SaveAudio",)
    assert "research_ledger" not in seen_payload


def test_batch_terminal_can_author_explicit_missing_classes_feedback() -> None:
    from vibecomfy.comfy_nodes.agent.edit import split_terminal_clarify

    terminal = split_terminal_clarify(
        'clarify("Which exact saver should research resolve?", '
        'missing_classes=["SaveAudio"])'
    )

    assert terminal.batch == ""
    assert terminal.message == "Which exact saver should research resolve?"
    assert terminal.missing_classes == ("SaveAudio",)

    plain = split_terminal_clarify("clarify(\"Which format do you prefer?\")")
    assert plain.missing_classes == ()


def test_batch_response_projects_only_explicit_feedback_terminal() -> None:
    from vibecomfy.comfy_nodes.agent._frag_response_contract import (
        _implement_missing_classes_feedback_payload,
    )

    state = SimpleNamespace(
        batch_implement_missing_classes_feedback=("SaveAudio",),
        user_message="Which exact saver should research resolve?",
        batch_turns=[
            {
                "statements": [
                    {
                        "detail": {
                            "missing_classes": ["SaveAudio"],
                            "tool_status": "no_results",
                        }
                    }
                ]
            }
        ],
    )

    payload = _implement_missing_classes_feedback_payload(state)
    assert payload == {
        "question": "Which exact saver should research resolve?",
        "missing_classes": ["SaveAudio"],
        "lookup_receipts": [
            {
                "node_class": "SaveAudio",
                "status": "no_results",
                "source": "implement",
            }
        ],
    }

    state.batch_implement_missing_classes_feedback = ()
    assert _implement_missing_classes_feedback_payload(state) is None


def test_feedback_research_preserves_prior_ledger_and_remaining_budget(
    monkeypatch,
) -> None:
    prior = _research_result(
        "original precedent",
        turns_used=3,
        executed_tool_calls=5,
        deadline_seconds=90.0,
        elapsed_seconds=20.0,
    )
    feedback = ImplementMissingClassesFeedback(
        question="Which exact authorable class provides FLAC output?",
        missing_classes=("SaveAudio",),
        lookup_receipts=(
            {"node_class": "SaveAudio", "status": "no_results", "source": "implement"},
        ),
    )
    seen: dict[str, Any] = {}

    def fake_stage(**kwargs: Any):
        seen.update(kwargs)
        current = _research_result(
            "ExactFlacSaver is the candidate",
            turns_used=2,
            executed_tool_calls=2,
        )
        return current.trace, current.evidence_pack

    monkeypatch.setattr(core, "run_agent_research_stage", fake_stage)

    result = core._run_agent_owned_research(
        ExecutorRequest(query="make it FLAC", graph={"nodes": [], "links": []}),
        SimpleNamespace(agent="test", model="test", effort="low"),
        plan=ClassifyDecision(intent="edit", route="adapt", research=True, implement=True),
        implement_feedback=feedback,
        prior_result=prior,
    )

    assert seen["max_turns"] == 5
    assert seen["deadline_seconds"] == 70.0
    assert seen["max_tool_calls"] == MAX_RESEARCH_TOOL_CALLS - 5
    assert seen["prior_ledger"] is prior.ledger
    conclusions = [entry.conclusion for entry in result.ledger.entries]
    assert conclusions[0] == "original precedent"
    assert any("SaveAudio" in conclusion for conclusion in conclusions)
    assert conclusions[-1] == "ExactFlacSaver is the candidate"
    assert result.package is not None
    assert result.package.budget["turns_used"] == 5
    assert result.package.budget["deadline_seconds"] == 90.0
    assert result.package.budget["tool_calls_used"] == 7
    assert result.package.budget["tool_calls_remaining"] == MAX_RESEARCH_TOOL_CALLS - 7


def test_resumed_research_first_decision_sees_prior_ledger_and_remaining_calls() -> None:
    prior = _research_result(
        "original precedent remains relevant",
        turns_used=3,
        executed_tool_calls=5,
    )
    seen: dict[str, str] = {}

    def judge(
        question: str,
        digest: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        del question, messages
        seen["digest"] = digest
        return {
            "action": "finish",
            "conclusion": "Retain the prior conclusion.",
            "evidence_ids": [],
            "uncertainty": "",
        }

    run_agent_research_stage(
        route="adapt",
        question="Which exact class should replace the missing saver?",
        judge_fn=judge,
        prior_ledger=prior.ledger,
        max_turns=1,
        max_tool_calls=MAX_RESEARCH_TOOL_CALLS - 5,
    )

    assert "original precedent remains relevant" in seen["digest"]
    assert "Evidence tool calls left: 7." in seen["digest"]


def test_feedback_phase_keeps_research_and_implement_tool_surfaces_partitioned() -> None:
    from vibecomfy.comfy_nodes.agent.provider import build_batch_messages
    from vibecomfy.executor.agent_research_stage import build_agent_research_messages
    from vibecomfy.executor.tool_specs import (
        IMPLEMENT_PHASE_TOOLS,
        RESEARCH_PHASE_TOOLS,
    )

    assert {"hivemind_search", "hivemind_get", "registry_lookup"} <= set(
        RESEARCH_PHASE_TOOLS
    )
    assert not {"hivemind_search", "hivemind_get", "registry_lookup"} & set(
        IMPLEMENT_PHASE_TOOLS
    )
    research_system = build_agent_research_messages(
        question="Which exact class is a candidate?",
        evidence_digest="No evidence gathered yet.",
        route="adapt",
    )[0]["content"]
    implement_system = build_batch_messages(
        task="resume after inventory research",
        tool_phase="implement",
    )[0]["content"]
    assert "hivemind_search" in research_system
    assert "registry_lookup" in research_system
    assert "hivemind_search" not in implement_system
    assert "hivemind_get" not in implement_system
    assert "registry_lookup" not in implement_system
    assert "node_schema" in implement_system


def test_catalog_backed_exact_class_can_rebaseline_frozen_snapshot() -> None:
    from vibecomfy.porting.edit._interpret import _frozen_provider_for_interpret
    from vibecomfy.schema import FrozenSchemaSnapshotProvider
    from vibecomfy.schema.types import (
        InputSpec,
        NodeSchema,
        OutputSpec,
        capture_schema_snapshot,
    )
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    catalog_schema = NodeSchema(
        class_type="ExactFlacSaver",
        pack="configured-test-pack",
        inputs={"audio": InputSpec("AUDIO", required=True)},
        outputs=[OutputSpec("AUDIO", "AUDIO")],
    )
    frozen = FrozenSchemaSnapshotProvider(
        capture_schema_snapshot(
            request_snapshot={"schemas": {}, "missing_classes": ["ExactFlacSaver"]}
        )
    )
    frozen._frozen_schema_catalog = {"ExactFlacSaver": catalog_schema}
    workflow = VibeWorkflow(
        id="inventory-feedback",
        source=WorkflowSource(id="inventory-feedback"),
        nodes={"1": VibeNode("1", "Source")},
    )

    completed = _frozen_provider_for_interpret(
        frozen,
        pre_workflow=workflow,
        batch_source='flac = node("ExactFlacSaver", audio=source.AUDIO)',
    )

    assert completed.snapshot.generation == frozen.snapshot.generation + 1
    admitted = completed.get_schema("ExactFlacSaver")
    assert admitted is not None
    assert admitted.class_type == "ExactFlacSaver"
    assert admitted.pack == "configured-test-pack"
    assert admitted.inputs["audio"].type == "AUDIO"
    assert "ExactFlacSaver" not in completed.snapshot.missing_classes


def test_repeated_exact_miss_preserves_clarify_and_records_budget(
    monkeypatch,
) -> None:
    implementations = 0
    research_calls = 0

    monkeypatch.setattr(
        core,
        "_resolve_spec",
        lambda *args, **kwargs: SimpleNamespace(agent="test", model="test", effort="low"),
    )
    monkeypatch.setattr(
        core,
        "_run_classify",
        lambda *args, **kwargs: ClassifyDecision(
            intent="edit", route="revise", research=False, implement=True, reply=True
        ),
    )

    def fake_research(*args: Any, **kwargs: Any) -> core.AgentResearchResult:
        nonlocal research_calls
        research_calls += 1
        return _research_result("No exact authorable candidate was established", turns_used=2)

    def fake_implement(*args: Any, **kwargs: Any) -> ImplementationResult:
        nonlocal implementations
        implementations += 1
        return _missing_result(outcome_kind="clarify")

    monkeypatch.setattr(core, "_run_agent_owned_research", fake_research)
    monkeypatch.setattr(core, "_run_implement", fake_implement)
    monkeypatch.setattr(
        core,
        "_run_reply",
        lambda *args, **kwargs: kwargs["implementation_result"].message,
    )

    result = core.run_executor(
        ExecutorRequest(
            query="Change SaveAudioMP3 to FLAC",
            graph={"nodes": [{"id": 1, "type": "SaveAudioMP3"}], "links": []},
        ),
        host_ports=_ports(),
    )

    assert result.ok is True
    assert implementations == 2
    assert research_calls == 1
    durable = result.report.implementation.durable_response
    terminal = durable["outcome"]
    assert terminal["kind"] == "clarify"
    assert terminal["missing_classes"] == ("SaveAudio",)
    assert "authoring_blocker" not in durable.get("report", {})
    exhausted = durable["report"]["inventory_feedback_budget"]
    assert exhausted["outcome_preserved"] is True
    assert exhausted["repeated_question"] is True
    assert exhausted["repeated_missing_classes"] is True
    assert result.reply == terminal["question"]


def test_different_second_feedback_preserves_agent_terminal_and_records_exhaustion(
    monkeypatch,
) -> None:
    second_question = "Should I keep the current output or add a preview instead?"
    implementations = iter(
        (
            _missing_result(),
            _missing_result(
                outcome_class="PreviewAudio",
                receipt_class="PreviewAudio",
                question=second_question,
                outcome_kind="clarify",
            ),
        )
    )

    monkeypatch.setattr(
        core,
        "_resolve_spec",
        lambda *args, **kwargs: SimpleNamespace(agent="test", model="test", effort="low"),
    )
    monkeypatch.setattr(
        core,
        "_run_classify",
        lambda *args, **kwargs: ClassifyDecision(
            intent="edit", route="revise", research=False, implement=True, reply=True
        ),
    )
    monkeypatch.setattr(
        core,
        "_run_agent_owned_research",
        lambda *args, **kwargs: _research_result("Try the admitted class", turns_used=2),
    )
    monkeypatch.setattr(
        core,
        "_run_implement",
        lambda *args, **kwargs: next(implementations),
    )
    monkeypatch.setattr(core, "_run_reply", lambda *args, **kwargs: second_question)

    result = core.run_executor(
        ExecutorRequest(
            query="Change SaveAudioMP3 to FLAC",
            graph={"nodes": [{"id": 1, "type": "SaveAudioMP3"}], "links": []},
        ),
        host_ports=_ports(),
    )

    durable = result.report.implementation.durable_response
    assert durable["outcome"]["kind"] == "clarify"
    assert durable["outcome"]["question"] == second_question
    assert durable["outcome"]["missing_classes"] == ("PreviewAudio",)
    exhausted = durable["report"]["inventory_feedback_budget"]
    assert exhausted["kind"] == "feedback_budget_exhausted"
    assert exhausted["prior_question"] == (
        "Which authorable class can save this output as FLAC?"
    )
    assert exhausted["current_question"] == second_question
    assert exhausted["outcome_preserved"] is True


def test_save_audio_mp3_receipt_does_not_satisfy_save_audio_exactness() -> None:
    result = _missing_result(
        outcome_class="SaveAudio",
        receipt_class="SaveAudioMP3",
    )

    assert core._implement_missing_classes_feedback(result) is None


def test_code_promoted_public_missing_classes_does_not_choose_feedback_edge() -> None:
    result = _missing_result(explicit_feedback=False)

    assert core._implement_missing_classes_feedback(result) is None


def _audio_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "SaveAudioMP3",
                "properties": {"vibecomfy_uid": "audio-saver"},
                "widgets_values": {
                    "filename_prefix": "audio/ComfyUI",
                    "quality": "320k",
                },
            }
        ],
        "links": [],
        "groups": [],
        "last_node_id": 1,
        "last_link_id": 0,
        "version": 0.4,
    }


class _AudioCatalog:
    def __init__(self, *, fail_lookup: bool = False) -> None:
        from vibecomfy.schema import InputSpec, NodeSchema

        self.fail_lookup = fail_lookup
        self._schema = NodeSchema(
            class_type="SaveAudioMP3",
            pack="audio-pack",
            inputs={
                "filename_prefix": InputSpec("STRING"),
                "quality": InputSpec("STRING"),
            },
            outputs=[],
            widget_input_order=("filename_prefix", "quality"),
            source_provider="object_info",
        )

    def get_schema(self, class_type: str):
        if self.fail_lookup and class_type == "SaveAudio":
            raise RuntimeError("schema provider offline")
        return self._schema if class_type == "SaveAudioMP3" else None

    def schemas(self):
        return {"SaveAudioMP3": self._schema}


def _run_real_terminal_orchestration(
    monkeypatch,
    tmp_path,
    responses: list[dict[str, str]],
    *,
    provider=None,
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
    from vibecomfy.comfy_nodes.agent import edit

    response_iter = iter(responses)
    implement_payloads: list[dict[str, Any]] = []
    research_calls: list[dict[str, Any]] = []
    active_provider = provider or _AudioCatalog()

    def handle_agent_edit(payload: dict[str, Any], **_kwargs: Any):
        implement_payloads.append(dict(payload))
        return edit.handle_agent_edit(
            payload,
            schema_provider=active_provider,
            deepseek_client=lambda _messages: next(response_iter),
            session_root=tmp_path / "sessions",
        )

    monkeypatch.setattr(
        core,
        "_resolve_spec",
        lambda *args, **kwargs: SimpleNamespace(
            agent="test", model="test", effort="low"
        ),
    )
    monkeypatch.setattr(
        core,
        "_run_classify",
        lambda *args, **kwargs: ClassifyDecision(
            intent="edit", route="revise", research=False, implement=True, reply=True
        ),
    )

    def fake_research(*args: Any, **kwargs: Any):
        research_calls.append(kwargs)
        return _research_result("No exact installed replacement established", turns_used=1)

    monkeypatch.setattr(core, "_run_agent_owned_research", fake_research)
    monkeypatch.setattr(
        core,
        "_run_reply",
        lambda request, spec, **kwargs: kwargs["implementation_result"].message,
    )
    result = core.run_executor(
        ExecutorRequest(
            query="Change this audio saver while preserving the graph.",
            graph=_audio_graph(),
            session_id="terminal-evidence-session",
            max_batches=4,
        ),
        host_ports=_ports(handle_agent_edit=handle_agent_edit),
    )
    return result, implement_payloads, research_calls


class TestBlockerEvidenceRealOrchestration:
    def test_generic_clarify_stays_clarify_without_choosing_a_blocker(
        self, monkeypatch, tmp_path
    ) -> None:
        question = "Which output format do you want?"
        result, payloads, research_calls = _run_real_terminal_orchestration(
            monkeypatch,
            tmp_path,
            [{"message": question, "batch": f'clarify("{question}")'}],
        )

        durable = result.report.implementation.durable_response
        assert durable["outcome"]["kind"] == "clarify"
        assert durable["outcome"]["question"] == question
        assert "implement_missing_classes_feedback" not in durable
        assert durable["report"]["implement_blocker_evidence"] == {
            "scope": "current_authoring_session",
            "unresolved_question": question,
            "lookup_receipts": (),
            "provider_errors": (),
        }
        assert len(payloads) == 1
        assert research_calls == []

    def test_explicit_missing_class_transports_exact_receipt_and_mp3_is_not_a_match(
        self, monkeypatch, tmp_path
    ) -> None:
        first = "Which exact class can replace the MP3 saver?"
        second = "Should I keep the current MP3 output for now?"
        result, payloads, research_calls = _run_real_terminal_orchestration(
            monkeypatch,
            tmp_path,
            [
                {
                    "message": "Checking the exact class.",
                    "batch": 'search(focus_types=["SaveAudio"])',
                },
                {
                    "message": first,
                    "batch": f'clarify("{first}", missing_classes=["SaveAudio"])',
                },
                {"message": second, "batch": f'clarify("{second}")'},
            ],
        )

        durable = result.report.implementation.durable_response
        assert len(research_calls) == 1
        feedback = research_calls[0]["implement_feedback"]
        assert feedback.missing_classes == ("SaveAudio",)
        assert feedback.lookup_receipts[0]["status"] == "no_results"
        assert payloads[1]["implement_feedback"]["missing_classes"] == ["SaveAudio"]
        assert durable["outcome"]["kind"] == "clarify"
        assert durable["outcome"]["question"] == second
        assert "SaveAudioMP3" not in {
            receipt["node_class"]
            for receipt in feedback.lookup_receipts
        }
        preserved = durable["report"]["inventory_feedback_budget"][
            "validated_inventory_feedback"
        ]
        assert preserved == {
            "scope": "implement_feedback_round",
            "question": first,
            "missing_classes": ("SaveAudio",),
            "lookup_receipts": (
                {
                    "node_class": "SaveAudio",
                    "status": "no_results",
                    "source": "implement",
                },
            ),
            "round_index": 1,
            "evidence_ids": ("implement_missing_classes:1",),
        }
        response_json = result.to_dict()
        projected = response_json["report"]["executor"]["implementation"][
            "diagnostics"
        ]["inventory_feedback_budget"]["validated_inventory_feedback"]
        assert projected == {
            "scope": "implement_feedback_round",
            "question": first,
            "missing_classes": ["SaveAudio"],
            "lookup_receipts": [
                {
                    "node_class": "SaveAudio",
                    "status": "no_results",
                    "source": "implement",
                }
            ],
            "round_index": 1,
            "evidence_ids": ["implement_missing_classes:1"],
        }
        assert response_json["outcome"]["kind"] == "clarify"
        assert response_json["outcome"]["kind"] != "requires_custom_nodes"

    def test_prior_receipts_keep_round_scope_when_plain_clarify_checks_other_classes(
        self, monkeypatch, tmp_path
    ) -> None:
        first = "Which exact class can replace the MP3 saver?"
        second = "Should I use the preview path instead?"
        result, _payloads, _research_calls = _run_real_terminal_orchestration(
            monkeypatch,
            tmp_path,
            [
                {
                    "message": "Checking the saver.",
                    "batch": 'search(focus_types=["SaveAudio"])',
                },
                {
                    "message": first,
                    "batch": f'clarify("{first}", missing_classes=["SaveAudio"])',
                },
                {
                    "message": "Checking the preview path.",
                    "batch": 'search(focus_types=["PreviewAudio"])',
                },
                {"message": second, "batch": f'clarify("{second}")'},
            ],
        )

        durable = result.report.implementation.durable_response
        current = durable["report"]["implement_blocker_evidence"]
        assert current["scope"] == "current_authoring_session"
        assert current["lookup_receipts"] == (
            {
                "node_class": "PreviewAudio",
                "status": "no_results",
                "source": "implement",
            },
        )
        assert "SaveAudio" not in {
            receipt["node_class"] for receipt in current["lookup_receipts"]
        }

        preserved = durable["report"]["inventory_feedback_budget"][
            "validated_inventory_feedback"
        ]
        assert preserved["scope"] == "implement_feedback_round"
        assert preserved["round_index"] == 1
        assert preserved["missing_classes"] == ("SaveAudio",)
        assert preserved["evidence_ids"] == ("implement_missing_classes:1",)
        assert durable["outcome"]["kind"] == "clarify"
        assert "missing_classes" not in durable["outcome"]
        assert "authoring_blocker" not in durable["report"]

    def test_schema_outage_is_not_serialized_as_absence(
        self, monkeypatch, tmp_path
    ) -> None:
        question = "Should I retry the schema lookup?"
        result, _payloads, research_calls = _run_real_terminal_orchestration(
            monkeypatch,
            tmp_path,
            [
                {
                    "message": "Checking the exact class.",
                    "batch": 'node_schema("SaveAudio")',
                },
                {"message": question, "batch": f'clarify("{question}")'},
            ],
            provider=_AudioCatalog(fail_lookup=True),
        )

        durable = result.report.implementation.durable_response
        evidence = durable["report"]["implement_blocker_evidence"]
        assert durable["outcome"]["kind"] == "clarify"
        assert evidence["lookup_receipts"] == (
            {
                "node_class": "SaveAudio",
                "status": "unavailable",
                "source": "implement",
            },
        )
        assert evidence["provider_errors"]
        assert research_calls == []

    def test_feedback_budget_never_rewrites_a_different_second_question(
        self, monkeypatch, tmp_path
    ) -> None:
        first = "Which exact class can replace the MP3 saver?"
        second = "Should I add a preview instead?"
        result, _payloads, _research_calls = _run_real_terminal_orchestration(
            monkeypatch,
            tmp_path,
            [
                {"message": "Checking.", "batch": 'search(focus_types=["SaveAudio"])'},
                {"message": first, "batch": f'clarify("{first}", missing_classes=["SaveAudio"])'},
                {"message": "Checking preview.", "batch": 'search(focus_types=["PreviewAudio"])'},
                {"message": second, "batch": f'clarify("{second}", missing_classes=["PreviewAudio"])'},
            ],
        )

        durable = result.report.implementation.durable_response
        assert durable["outcome"]["kind"] == "clarify"
        assert durable["outcome"]["question"] == second
        assert durable["report"]["inventory_feedback_budget"]["outcome_preserved"] is True

    def test_repeated_exact_miss_packages_evidence_without_selecting_refusal(
        self, monkeypatch, tmp_path
    ) -> None:
        question = "Which exact class can replace the MP3 saver?"
        result, _payloads, _research_calls = _run_real_terminal_orchestration(
            monkeypatch,
            tmp_path,
            [
                {"message": "Checking.", "batch": 'search(focus_types=["SaveAudio"])'},
                {"message": question, "batch": f'clarify("{question}", missing_classes=["SaveAudio"])'},
                {"message": "Checking again.", "batch": 'search(focus_types=["SaveAudio"])'},
                {"message": question, "batch": f'clarify("{question}", missing_classes=["SaveAudio"])'},
            ],
        )

        durable = result.report.implementation.durable_response
        assert durable["outcome"]["kind"] == "clarify"
        assert durable["outcome"]["question"] == question
        assert durable["outcome"]["missing_classes"] == ("SaveAudio",)
        assert "authoring_blocker" not in durable["report"]
        exhausted = durable["report"]["inventory_feedback_budget"]
        assert exhausted["outcome_preserved"] is True
        assert exhausted["repeated_question"] is True
