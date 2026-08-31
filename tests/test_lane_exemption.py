"""Action 3: expected_no_candidate exemption from answer_only + inspect blocker.

d813fe: apply:false + expect_graph_changed:false would stamp answer_only, which
cannot emit requires_custom_nodes. Typed-refusal contracts stay implement-capable.

673197: staged diagnostics under answer_only must take inspect/research, not
bare respond. Inspect synthesizes authoring_blocker.missing_runtime_classes so
promote_requires_custom_nodes_outcome can fire without the batch path.
"""

from __future__ import annotations

from typing import Any

import pytest

from vibecomfy.agent.contracts import HeadlessAgentRequest
from vibecomfy.comfy_nodes.agent.contracts import (
    missing_runtime_classes_from_report,
    promote_requires_custom_nodes_outcome,
)
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorHostPorts,
    ExecutorRequest,
)
from vibecomfy.executor.profiles import AgentSpecShape
from vibecomfy.executor.threaded import (
    ThreadedKernel,
    coerce_declared_interaction_lane,
    inspect_named_runtime_absences,
    inspect_refusal_evidence_ledger,
    run_threaded_executor,
    synthesize_inspect_refusal_implementation,
    typed_refusal_contract,
    _threaded_plan,
)


class _Failure:
    kind = type("Kind", (), {"value": "ValidationError"})()
    user_facing_message = "failed"


def _ports() -> ExecutorHostPorts:
    return ExecutorHostPorts(
        handle_agent_edit=lambda *a, **k: {},
        payload_hash=lambda payload: "hash",
        classify_failure=lambda *a, **k: _Failure(),
        failure_envelope=lambda *a, **k: _Failure(),
        begin_deepseek_usage_capture=lambda: object(),
        snapshot_deepseek_usage_capture=lambda: ({}, False),
        end_deepseek_usage_capture=lambda token: None,
        begin_model_attempt_capture=lambda: object(),
        snapshot_model_attempt_capture=lambda: (),
        end_model_attempt_capture=lambda token: None,
    )


def _d813fe_request(**overrides: Any) -> ExecutorRequest:
    payload = {
        "query": "Replace the SEGS detector with GroundingDINO",
        "graph": {"1": {"class_type": "UltralyticsDetectorProvider", "inputs": {}}},
        "interaction_mode": "answer_only",
        "expect_graph_changed": False,
        "allow_safe_refusal_outcome_kinds": ["requires_custom_nodes"],
        "expected_no_candidate_absent_classes": ["GroundingDINO"],
    }
    payload.update(overrides)
    return ExecutorRequest(**payload)


def test_d813fe_typed_refusal_remains_non_editing_in_answer_only() -> None:
    """Typed refusal metadata cannot override the answer-only authority."""
    plan = _threaded_plan(_d813fe_request())
    assert typed_refusal_contract(_d813fe_request()) is True
    assert plan.effective_route == "inspect"
    assert plan.implement is False
    assert plan.research is False


def test_explain_answer_only_without_typed_refusal_uses_inspect() -> None:
    request = ExecutorRequest(
        query="what could be causing the black frames in this workflow?",
        graph={"1": {"class_type": "KSampler", "inputs": {}}},
        interaction_mode="answer_only",
        expect_graph_changed=False,
    )
    plan = _threaded_plan(request)
    assert typed_refusal_contract(request) is False
    assert plan.effective_route == "inspect"
    assert plan.implement is False


def test_673197_staged_respond_is_lifted_to_inspect() -> None:
    """673197 staged: answer_only diagnostics must not stay on bare respond."""
    classified = ClassifyDecision(
        research=False,
        implement=False,
        reply=True,
        route="respond",
        task="answer",
        intent="respond",
        plan_summary="answer from the prompt",
    )
    request = ExecutorRequest(
        query="walk through the upscale sampler widgets",
        graph={"1": {"class_type": "KSampler", "inputs": {}}},
        interaction_mode="answer_only",
        expect_graph_changed=False,
    )
    plan = coerce_declared_interaction_lane(request, classified)
    assert plan.effective_route == "inspect"
    assert plan.implement is False
    assert plan.route != "respond"


def test_typed_refusal_inspect_classification_stays_inspect_in_answer_only() -> None:
    classified = ClassifyDecision(
        research=False,
        implement=False,
        reply=True,
        route="inspect",
        task="inspect_graph",
        intent="explain_graph",
    )
    plan = coerce_declared_interaction_lane(_d813fe_request(), classified)
    assert plan.effective_route == "inspect"
    assert plan.implement is False


def test_inspect_synthesizes_missing_runtime_classes_for_named_absence() -> None:
    request = _d813fe_request()

    def lookup(class_type: str) -> object | None:
        if class_type == "GroundingDINO":
            return None
        return object()

    missing = inspect_named_runtime_absences(request, schema_lookup=lookup)
    assert missing == ("GroundingDINO",)
    ledger = inspect_refusal_evidence_ledger(request, schema_lookup=lookup)
    implementation = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"requires_custom_nodes",'
            '"missing_classes":["GroundingDINO"],'
            f'"evidence":["{next(iter(ledger))}"],'
            '"reply":"GroundingDINO is not in this runtime."}'
        ),
        schema_lookup=lookup,
        evidence_handle=ledger,
    )
    assert implementation is not None
    durable = dict(implementation.durable_response or {})
    blocker = durable["report"]["authoring_blocker"]
    assert list(blocker["missing_runtime_classes"]) == ["GroundingDINO"]
    assert blocker["reason"] == "named_class_absent_from_schema"
    assert missing_runtime_classes_from_report(durable["report"]) == ("GroundingDINO",)
    promoted = durable["outcome"]
    assert promoted["kind"] == "requires_custom_nodes"
    assert list(promoted["missing_classes"]) == ["GroundingDINO"]


def test_inspect_does_not_fabricate_absence_when_lookup_unavailable() -> None:
    request = _d813fe_request()
    from vibecomfy.executor import threaded as threaded_mod

    def lookup(_class_type: str) -> object:
        return threaded_mod._LOOKUP_UNAVAILABLE

    assert inspect_named_runtime_absences(request, schema_lookup=lookup) == ()
    assert (
        synthesize_inspect_refusal_implementation(
            request, reply="cannot prove", schema_lookup=lookup
        )
        is None
    )


def test_inspect_lane_attaches_promoted_outcome_on_executor_result() -> None:
    inspect_request = ExecutorRequest(
        query="Replace the SEGS detector with GroundingDINO",
        graph={"1": {"class_type": "UltralyticsDetectorProvider", "inputs": {}}},
        interaction_mode="answer_only",
        expect_graph_changed=False,
    )

    def lookup(class_type: str) -> object | None:
        return None if class_type == "GroundingDINO" else object()

    ledger = inspect_refusal_evidence_ledger(inspect_request, schema_lookup=lookup)

    def run_inspect_reply(*_a: Any, **_k: Any) -> str:
        return (
            '{"kind":"requires_custom_nodes",'
            '"missing_classes":["GroundingDINO"],'
            f'"evidence":["{next(iter(ledger))}"],'
            '"reply":"GroundingDINO is not authorable here."}'
        )

    kernel = ThreadedKernel(
        resolve_spec=lambda profile, stage: AgentSpecShape("hermes", "model", "medium"),
        run_implement=lambda *a, **k: pytest.fail("inspect lane must not implement"),
        emit_phase=lambda *args, **kwargs: None,
        enforce_reply_grounding=lambda reply, **kwargs: reply,
        accepted_delta_ops=lambda implementation: (),
        implementation_landed_edit=lambda implementation: False,
        no_candidate_reason=lambda implementation: None,
        run_inspect_reply=run_inspect_reply,
    )

    import vibecomfy.executor.threaded as threaded_mod

    original = threaded_mod._default_schema_lookup
    threaded_mod._default_schema_lookup = lookup
    try:
        result = run_threaded_executor(
            inspect_request,
            kernel=kernel,
            host_ports=_ports(),
            executor_id="executor-inspect-blocker",
        )
    finally:
        threaded_mod._default_schema_lookup = original

    assert result.ok is True
    assert result.graph is None
    impl = result.report.implementation
    assert impl is not None
    durable = dict(impl.durable_response or {})
    assert list(durable["report"]["authoring_blocker"]["missing_runtime_classes"]) == ["GroundingDINO"]
    envelope = result.to_dict()
    assert envelope["outcome"]["kind"] == "requires_custom_nodes"
    assert envelope["outcome"]["missing_classes"] == ["GroundingDINO"]


def test_adapter_exempts_expected_no_candidate_from_answer_only() -> None:
    import os

    os.environ["VIBECOMFY_HEADLESS"] = "1"
    from tests.live_agentic_harness import adapter as harness_adapter

    captured: dict[str, Any] = {}

    class _Result:
        status = "ok"
        ok = True
        readiness = {}
        error = None
        response: dict[str, Any] = {}

    def fake_run_headless(request: HeadlessAgentRequest, **_kwargs: Any) -> _Result:
        captured["request"] = request
        return _Result()

    import vibecomfy.agent.service as service

    orig_run = service.run_headless
    service.run_headless = fake_run_headless
    try:
        explain = {
            "id": "explain",
            "query": "what does this workflow do?",
            "apply": False,
            "assessment": {"expect_graph_changed": False},
            "graph": {"nodes": {}, "links": []},
        }
        harness_adapter.run_headless_scenario(explain, output_base="/tmp/act3", tag="t")
        assert captured["request"].interaction_mode == "answer_only"

        d813fe = {
            "id": "d813fe",
            "query": "Replace the SEGS detector with GroundingDINO",
            "apply": False,
            "graph": {"nodes": {}, "links": []},
            "assessment": {
                "expect_graph_changed": False,
                "expected_no_candidate_reason": "GroundingDINO is absent",
                "expected_no_candidate_absent_classes": ["GroundingDINO"],
                "allow_safe_refusal_outcome_kinds": ["requires_custom_nodes"],
            },
        }
        harness_adapter.run_headless_scenario(d813fe, output_base="/tmp/act3", tag="t")
        req = captured["request"]
        assert req.interaction_mode != "answer_only"
        assert req.allow_safe_refusal_outcome_kinds == ("requires_custom_nodes",)
        assert req.expected_no_candidate_absent_classes == ("GroundingDINO",)
        executor = req.to_executor_request()
        assert typed_refusal_contract(executor) is True
        assert _threaded_plan(executor).implement is True
    finally:
        service.run_headless = orig_run


def test_promote_fires_from_synthesized_inspect_blocker() -> None:
    blocker_report = {
        "authoring_blocker": {
            "reason": "named_class_absent_from_schema",
            "missing_runtime_classes": ["MTCNN", "RetinaFace"],
        }
    }
    promoted = promote_requires_custom_nodes_outcome(
        {"kind": "noop"},
        missing_classes=missing_runtime_classes_from_report(blocker_report),
    )
    assert promoted["kind"] == "requires_custom_nodes"
    assert promoted["missing_classes"] == ["MTCNN", "RetinaFace"]
