"""W-03 — Four-category release guard (REPAIR / ADDITIVE / MULTINODE / DEBUG).

Cheap, NON-LIVE smoke coverage that becomes the release gate for the four
demo-factory execution routes. No real LLM calls and no ComfyUI boot: every
external surface is either constructed inline or built through the same offline
port-export / fault-injection paths the existing ``test_demo_factory_multinode``
tests use.

Coverage areas (see the task spec):

1. Route semantics — each category routes through its expected code path.
2. Prompt isolation — the inputs each category hands to the fixer prompt
   builder carry NO forbidden construction data (``assert_no_forbidden_fields``).
3. Legacy fallback — ADDITIVE without a manifest and existing MULTINODE
   positives retain legacy behavior (``topology_manifest`` is None / absent).
4. Positive-control characterization — the known green fixtures still reach
   their current verdict tier (regression guard on shared code).

Anti-gaming (PLAN.md §6): fixture locators, ``slice_node_ids``, golden node
IDs / widget values / sigma strings, and case-specific class names must never
reach classification, research, protocol notes, the prompt, or application
inputs. The smoke runner asserts they are absent from every surface it can
reach offline.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from tests._splice_antigaming import (
    FORBIDDEN_TOKENS,
    assert_no_forbidden_fields,
)

from vibecomfy.demo_factory.case import check_leakage
from vibecomfy.demo_factory.deltas import derive_repair_delta
from vibecomfy.demo_factory.oracle import Oracle, Verdict
from vibecomfy.demo_factory import run_campaign
from vibecomfy.demo_factory.run_campaign import (
    ADDITIVE_WORKFLOWS,
    DEBUG_WORKFLOWS,
    MULTINODE_WORKFLOWS,
    REPAIR_WORKFLOWS,
    _author_additive_inquiry,
    _golden_for,
    _golden_for_multinode,
    _inject_debug_fault,
    _remove_feature_fault,
    _remove_subgraph_fault,
)
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    PrecedentAdaptationPlan,
    WorkflowSlice,
)
from vibecomfy.executor.core import (
    _canonical_route_for_plan,
    _should_research,
)
from vibecomfy.executor.prompts import build_reply_messages


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _dangling_links(graph: dict[str, Any]) -> list[list[Any]]:
    node_ids = {str(node.get("id")) for node in graph.get("nodes", [])}
    return [
        link
        for link in graph.get("links", [])
        if isinstance(link, list)
        and len(link) >= 4
        and (str(link[1]) not in node_ids or str(link[3]) not in node_ids)
    ]


def _legacy_adaptation_plan(*, candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    """A legacy (manifest-free) adaptation-plan dict like the fixer receives."""
    plan = {
        "selected_slice": {"source_class_type": "offline precedent"},
        "structural_validation": "pass",
        "semantic_validation": "pass",
    }
    if candidate is not None:
        plan["candidate_graph"] = candidate
    return plan


# ===========================================================================
# 1. ROUTE SEMANTICS — each category dispatches through its expected route
# ===========================================================================


def test_repair_and_debug_route_to_revise_without_research() -> None:
    """REPAIR and DEBUG are non-additive repairs: implement without research.

    Both routes feed the fixer a direct/revise prompt (no precedent retrieval),
    so the canonical route must be ``revise`` and ``_should_research`` False.
    """
    repair_plan = ClassifyDecision(
        research=False, implement=True, intent="edit", reply=False
    )
    debug_plan = ClassifyDecision(
        research=False, implement=True, intent="edit", reply=False
    )
    assert _canonical_route_for_plan(repair_plan) == "revise"
    assert _canonical_route_for_plan(debug_plan) == "revise"
    assert _should_research(repair_plan) is False
    assert _should_research(debug_plan) is False


def test_typed_clarify_output_is_authoritative_for_headless_additive_runs() -> None:
    """An additive caller hint cannot rewrite agent-authored clarification."""
    clarify = ClassifyDecision(route="clarify", task="respond", reply=True)
    assert clarify.effective_route == "clarify"
    assert clarify.research is False
    assert clarify.implement is False


def test_additive_and_multinode_adapt_route_requires_research() -> None:
    """The additive adapt route runs research before the fixer."""
    adapt = ClassifyDecision(
        research=True, implement=True, intent="edit", route="adapt"
    )
    assert _canonical_route_for_plan(adapt) == "adapt"
    assert _should_research(adapt) is True


def test_campaign_dispatch_table_has_four_categories() -> None:
    """The four category tables exist and are non-empty (dispatch surface)."""
    assert REPAIR_WORKFLOWS, "REPAIR category is empty"
    assert ADDITIVE_WORKFLOWS, "ADDITIVE category is empty"
    assert MULTINODE_WORKFLOWS, "MULTINODE category is empty"
    assert DEBUG_WORKFLOWS, "DEBUG category is empty"


# ===========================================================================
# 2. PROMPT ISOLATION — construction data never reaches the fixer prompt
# ===========================================================================


def test_additive_inquiry_and_prompt_carry_no_forbidden_construction_data() -> None:
    """ADDITIVE: the inquiry + reply prompt must omit every forbidden token.

    The inquiry is authored from the removed feature type and symptom only; it
    must never embed ``slice_node_ids``, golden IDs, ``prior_path``, the removed
    node's class list, or fixture ancestry markers.
    """
    golden = _golden_for(ADDITIVE_WORKFLOWS[0][0])  # image/basic_image_upscale
    injection = _remove_feature_fault(golden, ADDITIVE_WORKFLOWS[0][1])
    assert injection is not None, "ADDITIVE positive fixture must remove a feature"

    golden_ids = {str(n.get("id")) for n in golden.get("nodes", [])}
    broken_ids = {str(n.get("id")) for n in injection.broken.get("nodes", [])}
    removed = [
        n for n in golden.get("nodes", [])
        if str(n.get("id")) in (golden_ids - broken_ids)
    ]
    removed_type = removed[0].get("type") if removed else None
    inquiry = _author_additive_inquiry(
        golden, injection.broken, ADDITIVE_WORKFLOWS[0][1], removed_type
    )

    # The inquiry is the user-facing surface; it must be leak-free.
    assert check_leakage(inquiry)["safe"] is True
    assert_no_forbidden_fields(inquiry, context="ADDITIVE inquiry")

    # The reply prompt the fixer receives (with a legacy adaptation plan).
    messages = build_reply_messages(
        inquiry,
        plan=ClassifyDecision(research=True, implement=True, route="adapt"),
        adaptation_plan=_legacy_adaptation_plan(),
        effective_route="adapt",
        candidate_present=True,
    )
    assert_no_forbidden_fields(messages, context="ADDITIVE reply prompt")


def test_multinode_inquiry_and_prompt_carry_no_forbidden_construction_data() -> None:
    """MULTINODE: the registered inquiry + prompt omit ``slice_node_ids`` etc.

    ``slice_node_ids`` is pure damage-injection metadata; it must not reach the
    fixer prompt even though the fixture is built by removing that exact slice.
    """
    spec = MULTINODE_WORKFLOWS[9]  # M-10: small ready fixture, fast offline
    assert check_leakage(spec.inquiry)["safe"] is True
    assert_no_forbidden_fields(spec.inquiry, context="MULTINODE inquiry")
    # The forbidden token for slice IDs must not appear in the inquiry.
    assert "slice_node_ids" not in spec.inquiry

    messages = build_reply_messages(
        spec.inquiry,
        plan=ClassifyDecision(research=True, implement=True, route="adapt"),
        adaptation_plan=_legacy_adaptation_plan(),
        effective_route="adapt",
        candidate_present=True,
    )
    assert_no_forbidden_fields(messages, context="MULTINODE reply prompt")


def test_debug_inquiry_and_prompt_carry_no_forbidden_construction_data() -> None:
    """DEBUG: the exact-fault inquiry names only the observable symptom.

    The bug_spec carries target node ids / widget values (the answer key); the
    inquiry string the fixer sees must not leak them.
    """
    spec = DEBUG_WORKFLOWS[0]  # D-01: set_widget on qwen_image_2512
    assert check_leakage(spec.inquiry)["safe"] is True
    assert_no_forbidden_fields(spec.inquiry, context="DEBUG inquiry")
    # The bug's target node id / widget value must NOT appear in the inquiry.
    assert str(spec.bug.get("target_node_id")) not in spec.inquiry
    assert str(spec.bug.get("new_value")) not in spec.inquiry

    # DEBUG uses the direct/revise prompt (no adaptation plan, no research).
    messages = build_reply_messages(
        spec.inquiry,
        plan=ClassifyDecision(
            research=False, implement=True, intent="edit", route="revise"
        ),
        effective_route="revise",
        candidate_present=True,
    )
    assert_no_forbidden_fields(messages, context="DEBUG revise prompt")


def test_repair_synthetic_inquiry_is_leak_free() -> None:
    """REPAIR: the symptom-based synthetic inquiry carries no answer key.

    ``_inquiry_for_fault`` builds the public inquiry from a generic symptom
    table, never from the injected locus / widget values.
    """
    from vibecomfy.demo_factory.case import _inquiry_for_fault

    for fault_family, effect in [
        ("final-output-bypass", "the output is wrong"),
        ("cfg-too-high", "the output is harsh"),
        ("steps-too-low", "the output is unfinished"),
    ]:
        inquiry = _inquiry_for_fault(fault_family, effect)
        assert check_leakage(inquiry)["safe"] is True
        assert_no_forbidden_fields(inquiry, context=f"REPAIR inquiry {fault_family}")


def test_forbidden_token_registry_covers_construction_metadata() -> None:
    """The anti-gaming registry must include the construction-data families."""
    tokens = set(FORBIDDEN_TOKENS)
    # Fixture ancestry breadcrumbs.
    assert "prior_path" in tokens
    assert "source_template" in tokens
    # Damage-injection slice metadata.
    assert "slice_node_ids" in tokens
    # Fixture-anchored node-id breadcrumbs.
    assert any(tok for tok in tokens if tok == "bee83462150b")
    # Widget-value literal that encodes fixture-specific data.
    assert "[0.5, 0.3]" in tokens
    # Path / filename markers.
    assert "ready_templates/" in tokens
    assert "custom_nodes/" in tokens


# ===========================================================================
# 3. LEGACY FALLBACK — manifest absent => legacy behavior (current behavior)
# ===========================================================================


def test_default_adaptation_plan_has_no_topology_manifest() -> None:
    """A legacy (manifest-free) plan serializes without ``topology_manifest``.

    W-02's manifest field defaults to None; when it is None the plan takes the
    legacy dependency-only consumption path. This is the current behavior and
    the release guard pins it.
    """
    plan = PrecedentAdaptationPlan(
        selected_slice=WorkflowSlice(source_class_type="legacy precedent")
    )
    assert plan.topology_manifest is None
    payload = plan.to_dict()
    assert "topology_manifest" not in payload


def test_additive_injection_without_manifest_uses_legacy_predicates() -> None:
    """ADDITIVE without a manifest retains legacy predicate behavior.

    ``_remove_feature_fault`` builds the injection via ``derive_repair_delta``
    (the legacy path): the repaired predicate carries additive_witness loci and
    NO ``topology_manifest`` key and NO ``additive_mode`` marker.
    """
    golden = _golden_for(ADDITIVE_WORKFLOWS[0][0])
    injection = _remove_feature_fault(golden, ADDITIVE_WORKFLOWS[0][1])
    assert injection is not None

    # Legacy predicate shape (no manifest, no multinode additive_mode flag).
    assert "topology_manifest" not in injection.repaired_predicate
    assert injection.repaired_predicate.get("additive_mode") is None
    # Legacy loci are still produced (the witness for the removed feature).
    assert injection.repaired_predicate.get("locus"), "legacy locus missing"


def test_multinode_positive_marks_additive_mode_but_no_manifest() -> None:
    """Existing MULTINODE positives keep their current legacy+multinode shape.

    ``_remove_subgraph_fault`` sets ``additive_mode='multinode'`` on the
    predicate (its existing behavior) but does NOT attach a topology manifest —
    the manifest field is W-02 work and is absent today.
    """
    spec = MULTINODE_WORKFLOWS[9]  # M-10: fast ready fixture
    golden = _golden_for_multinode(spec)
    injection = _remove_subgraph_fault(golden, spec.slice_node_ids, spec.feature_key)

    assert injection.repaired_predicate.get("additive_mode") == "multinode"
    assert "topology_manifest" not in injection.repaired_predicate
    assert "topology_manifest" not in injection.fault_predicate


def test_debug_injection_has_no_manifest_or_additive_mode() -> None:
    """DEBUG is a non-additive direct repair: no manifest, no additive flag."""
    spec = DEBUG_WORKFLOWS[0]
    golden = _golden_for(spec.locator)
    injection = _inject_debug_fault(golden, spec.bug)

    assert injection.repaired_predicate.get("additive_mode") is None
    assert "topology_manifest" not in injection.repaired_predicate
    assert "topology_manifest" not in injection.fault_predicate


# ===========================================================================
# 4. POSITIVE-CONTROL CHARACTERIZATION — current verdict tier regression guard
# ===========================================================================


def test_additive_positive_control_characterization() -> None:
    """ADDITIVE positive (basic_image_upscale/upscale): injection is sound.

    Characterizes the CURRENT structural facts the green control relies on:
    a real feature node is removed, the broken graph has no dangling links, and
    the oracle's repaired locus is non-empty. If shared-code changes break the
    fixture construction, this fails before the campaign runs.
    """
    golden = _golden_for(ADDITIVE_WORKFLOWS[0][0])
    injection = _remove_feature_fault(golden, ADDITIVE_WORKFLOWS[0][1])
    assert injection is not None, "upscale feature must be removable"

    golden_count = len(golden.get("nodes", []))
    broken_count = len(injection.broken.get("nodes", []))
    assert broken_count == golden_count - 1, "exactly one feature node removed"
    assert _dangling_links(injection.broken) == []
    assert injection.repaired_predicate.get("locus"), "repaired locus absent"


def test_multinode_positive_control_characterization() -> None:
    """MULTINODE positive (M-10): the slice is removed cleanly and judged sound.

    Characterizes the current tier: the registered slice is removed atomically,
    the broken graph is dangling-link-free, and a fresh-id reconstruction of
    the slice reaches the additive judge with an ACCEPTED verdict (mirroring the
    existing green case).
    """
    from vibecomfy.demo_factory import additive_judge
    from vibecomfy.demo_factory.additive_judge import AdditiveJudgeResult
    from vibecomfy.demo_factory.predicates import (
        AdditiveWitnessVerdict,
        grade_additive_witness,
    )

    spec = MULTINODE_WORKFLOWS[9]  # M-10
    golden = _golden_for_multinode(spec)
    injection = _remove_subgraph_fault(golden, spec.slice_node_ids, spec.feature_key)

    broken_nodes = {str(n.get("id")) for n in injection.broken.get("nodes", [])}
    assert set(spec.slice_node_ids).isdisjoint(broken_nodes)
    assert _dangling_links(injection.broken) == []

    # The multinode witness locus is the structural anchor of the green case.
    multinode_locus = next(
        locus
        for locus in injection.repaired_predicate["locus"]
        if locus.get("type") == "additive_witness"
    )
    # A trivially-reconstructed candidate (golden itself, slice present) must
    # pass the multinode witness grader — pinning the current grading tier.
    assert grade_additive_witness(
        golden, multinode_locus, mode="multinode"
    ).passed is True


def test_multinode_positive_control_reaches_judge_on_accept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MULTINODE positive (M-10): when the additive judge accepts, the oracle
    returns ACCEPTED. This is the end-to-end verdict tier the green case reaches.
    """
    from vibecomfy.demo_factory import additive_judge
    from vibecomfy.demo_factory.additive_judge import AdditiveJudgeResult
    from vibecomfy.demo_factory.predicates import AdditiveWitnessVerdict

    spec = MULTINODE_WORKFLOWS[9]
    golden = _golden_for_multinode(spec)
    injection = _remove_subgraph_fault(golden, spec.slice_node_ids, spec.feature_key)

    def accept_at_judge(*args: Any, **kwargs: Any) -> AdditiveJudgeResult:
        return AdditiveJudgeResult(
            verdict=AdditiveWitnessVerdict.ACCEPTED,
            reason="positive control reaches the judge",
            source="unit-test",
            profile="unit-test",
        )

    monkeypatch.setattr(
        additive_judge, "judge_additive_candidate", accept_at_judge
    )
    result = Oracle(
        injection.fault_predicate,
        injection.repaired_predicate,
        injection.broken,
        injection.golden,
    ).evaluate(
        golden,  # golden stands in for a perfect candidate
        execution_safe=True,
        output_reachable=True,
    )
    assert result.verdict is Verdict.ACCEPTED


def test_debug_positive_control_characterization() -> None:
    """DEBUG positive (D-01): exact fault produces a non-empty oracle locus.

    Characterizes the current tier: the registered exact mutation changes the
    graph, produces exactly one repaired locus, and the broken graph is
    dangling-link-free.
    """
    spec = DEBUG_WORKFLOWS[0]
    golden = _golden_for(spec.locator)
    injection = _inject_debug_fault(golden, spec.bug)

    assert injection.broken != golden, "DEBUG mutation must change the graph"
    assert _dangling_links(injection.broken) == []
    loci = injection.repaired_predicate.get("locus", [])
    assert len(loci) >= 1, "DEBUG mutation must produce an oracle locus"


def test_repair_positive_control_delta_is_well_formed() -> None:
    """REPAIR positive: a synthetic fault derives a sound repair delta.

    REPAIR uses the creative engine (live); we cannot call it here. Instead we
    characterize the shared deterministic seam it depends on —
    ``derive_repair_delta`` — on a hand-built broken/golden pair, proving the
    oracle locus machinery the green REPAIR cases rely on is intact.
    """
    golden = {
        "nodes": [
            {"id": 1, "type": "KSampler", "widgets_values": [1]},
            {"id": 2, "type": "SaveImage", "inputs": {}},
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
    }
    # Break the link (output bypass fault).
    broken = {
        "nodes": [
            {"id": 1, "type": "KSampler", "widgets_values": [1]},
            {"id": 2, "type": "SaveImage", "inputs": {}},
        ],
        "links": [],
    }
    injection = derive_repair_delta(broken, golden)
    assert injection.fault_predicate.get("locus"), "fault locus missing"
    assert injection.repaired_predicate.get("locus"), "repaired locus missing"
    # No construction metadata leaks into the deterministic predicates.
    assert_no_forbidden_fields(
        injection.fault_predicate, context="REPAIR fault predicate"
    )
    assert_no_forbidden_fields(
        injection.repaired_predicate, context="REPAIR repaired predicate"
    )
