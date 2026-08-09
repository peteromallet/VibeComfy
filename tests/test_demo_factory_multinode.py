from __future__ import annotations

import copy
import importlib
import json
from types import SimpleNamespace
from typing import Any

import pytest

from vibecomfy.demo_factory import additive_judge
from vibecomfy.demo_factory.additive_judge import AdditiveJudgeResult
from vibecomfy.demo_factory.baseline import port_check_graph
from vibecomfy.demo_factory.case import check_leakage
from vibecomfy.demo_factory.deltas import derive_repair_delta
from vibecomfy.demo_factory.oracle import Oracle, Verdict
from vibecomfy.demo_factory.predicates import (
    AdditiveWitnessVerdict,
    grade_additive_witness,
)
from vibecomfy.demo_factory import run_campaign
from vibecomfy.demo_factory.run_campaign import (
    MULTINODE_WORKFLOWS,
    MultinodeFixtureError,
    _golden_for_multinode,
    _remove_subgraph_fault,
    run_multinode_case,
)


def _fresh_id_reconstruction(
    golden: dict[str, Any],
    removed_ids: tuple[str, ...],
) -> dict[str, Any]:
    candidate = copy.deepcopy(golden)
    renamed = {
        node_id: str(1001 + index)
        for index, node_id in enumerate(removed_ids)
    }
    for node in candidate["nodes"]:
        old_id = str(node.get("id"))
        if old_id in renamed:
            node["id"] = int(renamed[old_id])
    for link in candidate["links"]:
        source_id = str(link[1])
        target_id = str(link[3])
        if source_id in renamed:
            link[1] = int(renamed[source_id])
        if target_id in renamed:
            link[3] = int(renamed[target_id])
    return candidate


def _dangling_links(graph: dict[str, Any]) -> list[list[Any]]:
    node_ids = {str(node.get("id")) for node in graph.get("nodes", [])}
    return [
        link
        for link in graph.get("links", [])
        if isinstance(link, list)
        and len(link) >= 4
        and (str(link[1]) not in node_ids or str(link[3]) not in node_ids)
    ]


def test_multinode_table_has_ten_explicit_unique_fixtures() -> None:
    assert [spec.case_id for spec in MULTINODE_WORKFLOWS] == [
        f"M-{index:02d}" for index in range(1, len(MULTINODE_WORKFLOWS) + 1)
    ]
    ready = sum(spec.kind == "ready" for spec in MULTINODE_WORKFLOWS)
    corpus = sum(spec.kind == "corpus" for spec in MULTINODE_WORKFLOWS)
    assert ready + corpus == len(MULTINODE_WORKFLOWS)
    assert corpus >= 2  # keep at least the original corpus coverage
    for spec in MULTINODE_WORKFLOWS:
        assert len(spec.slice_node_ids) >= 5
        assert len(set(spec.slice_node_ids)) == len(spec.slice_node_ids)
        assert spec.inquiry
        assert check_leakage(spec.inquiry)["safe"] is True


def test_all_multinode_fixtures_remove_exact_slice_without_dangling_links() -> None:
    for spec in MULTINODE_WORKFLOWS:
        golden = _golden_for_multinode(spec)
        injection = _remove_subgraph_fault(
            golden,
            spec.slice_node_ids,
            spec.feature_key,
        )
        golden_nodes = {
            str(node.get("id")): node for node in golden.get("nodes", [])
        }
        broken_nodes = {
            str(node.get("id")): node
            for node in injection.broken.get("nodes", [])
        }

        assert set(spec.slice_node_ids).isdisjoint(broken_nodes)
        assert len(golden_nodes) - len(broken_nodes) == len(spec.slice_node_ids)
        assert _dangling_links(injection.broken) == []
        for node_id, broken_node in broken_nodes.items():
            golden_node = golden_nodes[node_id]
            assert broken_node.get("type") == golden_node.get("type")
            assert broken_node.get("widgets_values") == golden_node.get("widgets_values")
            assert broken_node.get("properties") == golden_node.get("properties")


def test_m10_existing_loci_reject_fresh_internal_ids_but_multinode_reaches_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = next(s for s in MULTINODE_WORKFLOWS if s.case_id == "M-10")
    golden = _golden_for_multinode(spec)
    injection = _remove_subgraph_fault(
        golden,
        spec.slice_node_ids,
        spec.feature_key,
    )
    candidate = _fresh_id_reconstruction(golden, spec.slice_node_ids)

    assert len(golden["nodes"]) == 10
    assert len(injection.broken["nodes"]) == 5
    assert _dangling_links(injection.broken) == []

    legacy = derive_repair_delta(injection.broken, golden)
    legacy_loci = [
        locus
        for locus in legacy.repaired_predicate["locus"]
        if locus.get("type") == "additive_witness"
    ]
    assert len(legacy_loci) == 5
    assert all(
        not grade_additive_witness(candidate, locus).passed
        for locus in legacy_loci
    )

    multinode_locus = next(
        locus
        for locus in injection.repaired_predicate["locus"]
        if locus.get("type") == "additive_witness"
    )
    assert grade_additive_witness(
        candidate,
        multinode_locus,
        mode="multinode",
    ).passed
    candidate_ok, compile_error, _ = port_check_graph(candidate)
    assert candidate_ok, compile_error

    judge_reached = False

    def accept_at_judge(*args: Any, **kwargs: Any) -> AdditiveJudgeResult:
        nonlocal judge_reached
        judge_reached = True
        return AdditiveJudgeResult(
            verdict=AdditiveWitnessVerdict.ACCEPTED,
            reason="fresh-id reconstructed subgraph reached the existing judge",
            source="llm",
            profile="unit-test",
        )

    monkeypatch.setattr(
        additive_judge,
        "judge_additive_candidate",
        accept_at_judge,
    )
    result = Oracle(
        injection.fault_predicate,
        injection.repaired_predicate,
        injection.broken,
        injection.golden,
    ).evaluate(
        candidate,
        execution_safe=candidate_ok,
        output_reachable=candidate_ok,
    )
    assert judge_reached is True
    assert result.verdict is Verdict.ACCEPTED
    assert all(gate.passed for gate in result.gates)


def test_corpus_preflight_unresolved_class_is_fixture_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_spec = next(
        spec for spec in MULTINODE_WORKFLOWS if spec.kind == "corpus"
    )
    monkeypatch.setattr(run_campaign, "get_class", lambda class_type: None)
    with pytest.raises(MultinodeFixtureError, match="object_info cannot resolve"):
        _golden_for_multinode(corpus_spec)


def test_run_multinode_case_skips_fixture_error_before_fixer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    spec = MULTINODE_WORKFLOWS[0]
    monkeypatch.setattr(
        run_campaign,
        "_golden_for_multinode",
        lambda ignored: (_ for _ in ()).throw(
            MultinodeFixtureError("selected class is unavailable")
        ),
    )
    fixer_called = False

    def forbidden_fixer(*args: Any, **kwargs: Any) -> None:
        nonlocal fixer_called
        fixer_called = True
        raise AssertionError("fixture errors must not reach the fixer")

    monkeypatch.setattr(run_campaign, "_run_fixer", forbidden_fixer)
    result = run_multinode_case(spec, 1, tmp_path)
    assert result["verdict"] == "skipped_fixture_error"
    assert "fixture_error" in result
    assert fixer_called is False


def test_multinode_synthesis_rejects_unresolvable_then_retries_next_slice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    from vibecomfy.executor.contracts import WorkflowSlice

    research_module = importlib.import_module("vibecomfy.executor.research")
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(
        json.dumps({
            "10": {
                "class_type": "550e8400-e29b-41d4-a716-446655440000",
                "inputs": {"conditioning": ["11", 0]},
            },
            "11": {"class_type": "KSampler", "inputs": {}},
        }),
        encoding="utf-8",
    )
    second_path.write_text(
        json.dumps({
            "20": {
                "class_type": "ControlNetApplyAdvanced",
                "inputs": {"conditioning": ["21", 0]},
            },
            "21": {"class_type": "KSampler", "inputs": {}},
        }),
        encoding="utf-8",
    )
    slices = (
        WorkflowSlice(
            source_class_type="first precedent",
            source_workflow_path=str(first_path),
            node_ids=("10", "11"),
            node_types=("550e8400-e29b-41d4-a716-446655440000", "KSampler"),
            entry_anchor="11",
        ),
        WorkflowSlice(
            source_class_type="control precedent",
            source_workflow_path=str(second_path),
            node_ids=("20", "21"),
            node_types=("ControlNetApplyAdvanced", "KSampler"),
            entry_anchor="21",
        ),
    )
    target = {
        "1": {"class_type": "KSampler", "inputs": {}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }
    monkeypatch.setattr(
        research_module,
        "_runtime_object_info_resolves_class",
        lambda class_type: class_type in {
            "ControlNetApplyAdvanced",
            "KSampler",
            "SaveImage",
        },
    )

    plan = research_module._build_adaptation_plan(
        query="restore the missing ControlNet branch",
        graph=target,
        inspection=None,
        slices=slices,
    )

    assert plan is not None
    assert plan.semantic_validation == "pass"
    assert plan.selected_slice == slices[1]
    assert plan.candidate_graph is not None
    assert any(
        warning.get("code") == "synthesis_unresolvable_class"
        and warning.get("slice_rank") == 1
        for warning in plan.warnings
    )


def test_multinode_contract_drops_semantically_failed_candidate() -> None:
    from vibecomfy.executor.contracts import (
        PrecedentAdaptationPlan,
        WorkflowSlice,
    )

    plan = PrecedentAdaptationPlan(
        selected_slice=WorkflowSlice(source_class_type="precedent"),
        candidate_graph={"1": {"class_type": "KSampler", "inputs": {}}},
        structural_validation="pass",
        semantic_validation="fail",
    )

    assert plan.candidate_graph is None
    assert "candidate_graph" not in plan.to_dict()


def test_multinode_dependency_preflight_skips_annotations_and_retries_poisoned_plan() -> None:
    from vibecomfy.comfy_nodes.agent.edit import (
        _actionable_plan_required_new_classes,
        _retry_after_dependency_preflight_failure,
    )

    # W-07 contract: the candidate graph is the legacy path's primary
    # completeness witness and filters UI-only annotation classes; the
    # advisory ``required_new_nodes`` list no longer filters them.  The
    # annotations therefore live on the candidate graph, and derivation must
    # skip them while keeping the real class.
    plan = {
        "required_new_nodes": [{"class_type": "RealFeatureNode"}],
        "candidate_graph": {
            "1": {"class_type": "KSampler", "inputs": {}},
            "2": {"class_type": "Note", "inputs": {}},
            "3": {"class_type": "MarkdownNote", "inputs": {}},
            "4": {"class_type": "RealFeatureNode", "inputs": {}},
        },
    }
    state = SimpleNamespace(
        guard_original_ui=None,
        graph={"1": {"class_type": "KSampler", "inputs": {}}},
        route="adapt",
        execution_protocol_notes={
            "adaptation_plan": plan,
            "adaptation_plan_actionability": {"actionability": "actionable"},
        },
        executor_adaptation_plan=plan,
    )

    assert _actionable_plan_required_new_classes(state, plan) == (
        "RealFeatureNode",
    )
    _retry_after_dependency_preflight_failure(
        state,
        ("RealFeatureNode",),
    )
    assert "adaptation_plan" not in state.execution_protocol_notes
    assert state.execution_protocol_notes["synthesis_retry"]["trigger"] == (
        "dependency_preflight_failed"
    )
    assert state.execution_protocol_notes["synthesis_retry"][
        "rejected_class_types"
    ] == ["RealFeatureNode"]
    assert state.execution_protocol_notes["adaptation_plan_actionability"] == {
        "actionability": "non_actionable",
        "non_actionable_reason": "dependency_preflight_failed_retry_synthesis",
    }
    assert state.executor_adaptation_plan is None


def test_multinode_headless_additive_clarify_falls_through_to_research() -> None:
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import _headless_clarify_research_plan

    request = ExecutorRequest(
        query="restore the removed capability",
        graph={"nodes": [{"id": 1, "type": "KSampler"}], "links": []},
    )
    clarify = ClassifyDecision(route="clarify", task="respond")

    fallback = _headless_clarify_research_plan(
        request,
        clarify,
        additive=True,
    )
    assert fallback is not None
    assert fallback.effective_route == "adapt"
    assert fallback.research is True
    assert fallback.implement is True
    assert fallback.research_goal == request.query
    assert _headless_clarify_research_plan(
        request,
        clarify,
        additive=False,
    ) is None


def test_multinode_fixer_failure_writes_fingerprint_and_status(
    tmp_path: Any,
) -> None:
    from vibecomfy.demo_factory.case import Case, _fixer_gate

    case_dir = tmp_path / "case"
    attempt_dir = case_dir / "attempts" / "001"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "classification.json").write_text(
        json.dumps({
            "route": "clarify",
            "research": False,
            "implement": False,
        }),
        encoding="utf-8",
    )
    case = Case(
        case_id="opaque",
        case_dir=case_dir,
        source="multinode",
    )
    fixer_result = SimpleNamespace(
        ok=False,
        candidate=None,
        infra_blocked=False,
        error="no candidate",
        status="executor_failure",
    )

    assert _fixer_gate(case, fixer_result) is False
    assert case.verdict is Verdict.FIXER_FAILED
    fingerprint = json.loads(
        (attempt_dir / "failure_fingerprint.json").read_text(encoding="utf-8")
    )
    assert fingerprint["primary_reason_code"] == "CLASSIFY_NO_RESEARCH"
    status = json.loads(
        (case_dir / "status.json").read_text(encoding="utf-8")
    )
    assert status["verdict"] == "fixer_failed"
    assert status["failure_fingerprint"] == {
        "primary_code": "CLASSIFY_NO_RESEARCH",
        "counts": {"CLASSIFY_NO_RESEARCH": 1},
    }
