from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    PrecedentAdaptationPlan,
    ResearchResult,
    WorkflowSlice,
)
from vibecomfy.executor.profiles import AgentSpecShape

research_module = import_module("vibecomfy.executor.research")
core_module = import_module("vibecomfy.executor.core")
_should_prefetch_research = core_module._should_prefetch_research


def _source_workflow() -> dict:
    nodes = {
        "1": {
            "id": 1,
            "type": "ManualSigmas",
            "widgets_values": ["base-schedule"],
            "outputs": [{"name": "SIGMAS"}],
        },
        "2": {
            "id": 2,
            "type": "ManualSigmas",
            "widgets_values": ["refine-schedule"],
            "outputs": [{"name": "SIGMAS"}],
        },
        "3": {"id": 3, "type": "KSampler", "inputs": [{"name": "sigmas"}]},
        "4": {"id": 4, "type": "KSampler", "inputs": [{"name": "sigmas"}]},
    }
    return {
        "nodes": nodes,
        "links": [
            {"origin_id": 1, "origin_slot": 0, "target_id": 3, "target_slot": 0},
            {"origin_id": 2, "origin_slot": 0, "target_id": 4, "target_slot": 0},
        ],
    }


def _provenance_graph() -> dict:
    return {
        "extra": {"vibecomfy": {"source_template": "fixture/template"}},
        "nodes": [
            {"id": 10, "type": "ManualSigmas"},
            {"id": 11, "type": "ManualSigmas"},
        ],
        "links": [],
    }


def test_duplicate_type_slices_preserve_all_tagged_instances(monkeypatch) -> None:
    monkeypatch.setattr(
        research_module.provenance,
        "load_source_workflow",
        lambda _graph: _source_workflow(),
    )

    result = research_module.research(
        "add a sigma schedule node",
        graph=_provenance_graph(),
        target_node_type="ManualSigmas",
        local_limit=0,
        hivemind_client=None,
        registry_resolver=None,
        web_search_client=None,
    )

    assert len(result.precedent_slices) == 2
    assert {slice_.node_ids for slice_ in result.precedent_slices} == {("1",), ("2",)}
    values = {
        slice_.node_ids[0]: slice_.widget_values[0]["value"]
        for slice_ in result.precedent_slices
    }
    assert values == {"1": "base-schedule", "2": "refine-schedule"}
    assert all(
        widget["provenance"] == "source_template"
        and widget["confidence"] == "high"
        for slice_ in result.precedent_slices
        for widget in slice_.widget_values
    )
    assert all(slice_.role_label for slice_ in result.precedent_slices)
    assert result.precedent_slices[1].role_label == "refinement"
    assert result.precedent_slices[1].role_confidence == "medium"
    assert all(slice_.incident_edges for slice_ in result.precedent_slices)
    assert result.adaptation_plan is not None
    assert "provenance: source_template" in result.adaptation_plan.context_note
    assert "not a prescription" in result.adaptation_plan.context_note


def test_provenance_lookup_runs_before_corpus_and_falls_into_slices(monkeypatch) -> None:
    calls: list[str] = []

    def _load(graph):
        calls.append("load")
        return _source_workflow()

    def _local(*_args, **_kwargs):
        calls.append("corpus")
        return SimpleNamespace(sources=(), warnings=(), warning_details=())

    monkeypatch.setattr(research_module.provenance, "load_source_workflow", _load)
    monkeypatch.setattr(research_module, "run_local_research", _local)

    result = research_module.research(
        "add a sigma schedule node",
        graph=_provenance_graph(),
        target_node_type="ManualSigmas",
        hivemind_client=None,
        registry_resolver=None,
        web_search_client=None,
    )

    assert calls == ["load", "corpus"]
    assert len(result.precedent_slices) == 2
    assert result.sources[0]["provenance_lookup"] is True


def test_revise_keeps_case_00_cheap_but_allows_uncertain_provenance_research() -> None:
    plan = ClassifyDecision(
        route="revise",
        task="edit_graph",
        intent="edit",
        change_goal="add a ManualSigmas node",
        target_node_type="ManualSigmas",
    )
    cheap_request = ExecutorRequest(
        query="add a ManualSigmas node in the obvious linear slot",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    assert _should_prefetch_research(plan) is False
    assert _should_prefetch_research(plan, request=cheap_request) is False

    uncertain_request = ExecutorRequest(
        query="add the second-stage sigma schedule for the refinement branch",
        graph={
            **_provenance_graph(),
            "links": [
                {"origin_id": 10, "target_id": 20},
                {"origin_id": 10, "target_id": 21},
            ],
        },
    )
    assert _should_prefetch_research(plan, request=uncertain_request) is True


def test_fixer_handoff_contains_provenance_slices_and_prior_context(monkeypatch) -> None:
    captured: dict = {}
    source_slice = WorkflowSlice(
        source_class_type="ManualSigmas",
        node_ids=("1",),
        source_template="fixture/template",
        role_label="sampling",
        role_confidence="medium",
        widget_values=(
            {
                "name": "schedule",
                "value": "base-schedule",
                "provenance": "source_template",
                "confidence": "high",
            },
        ),
        incident_edges=(
            {"peer_class": "KSampler", "socket": "SIGMAS", "direction": "out"},
        ),
    )

    def _fake_edit(payload, **_kwargs):
        captured.update(payload)
        return {"ok": True, "graph": payload["graph"], "message": "evidence inspected"}

    monkeypatch.setattr(core_module, "handle_agent_edit", _fake_edit)
    request = ExecutorRequest(
        query="add a ManualSigmas node",
        graph={"nodes": [{"id": 10, "type": "KSampler"}], "links": []},
    )
    plan = ClassifyDecision(
        route="revise",
        task="edit_graph",
        intent="edit",
        change_goal="add a ManualSigmas node",
        target_node_type="ManualSigmas",
    )
    result = core_module._run_implement(
        request,
        AgentSpecShape(agent="hermes", model="test", effort="low"),
        plan=plan,
        research_result=ResearchResult(
            precedent_slices=(source_slice,),
            adaptation_plan=PrecedentAdaptationPlan(
                selected_slice=source_slice,
                all_slices=(source_slice,),
                context_note=(
                    "The source template used a value here (provenance: "
                    "source_template, confidence: high); treat it as a prior."
                ),
            ),
        ),
    )

    assert result.graph == request.graph
    assert captured["precedent_slices"][0]["widget_values"][0]["provenance"] == "source_template"
    assert captured["precedent_slices"][0]["role_label"] == "sampling"
    assert "provenance: source_template" in captured["adaptation_plan"]["context_note"]
