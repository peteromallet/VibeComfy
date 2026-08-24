"""Grounded expected-no-candidate adjudication (DEEP-AUDIT-FIX-4-REVISION).

Finding 001: declaring ``assessment.expected_no_candidate_reason`` must opt a
scenario into GROUNDED refusal adjudication — the envelope needs the declared
refusal kind on a canonical non-edit route plus structured absence evidence —
instead of acting as a blanket pass-loosener for any generic clarify. These
tests are deterministic and offline: the declared path never invokes an LLM
judge, so pass/fail is decided by assessor-checked structured evidence alone.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.live_agentic_harness.assessor import assess_live_output_dir
from tests.live_agentic_harness.scenario_obligations import (
    load_scenario_obligation,
    validate_obligation_coverage,
)

SCENARIOS_DIR = Path(__file__).parent / "live_agentic_harness" / "scenarios"

D813FE = "image-kolors-image-generation-with-segs-detailer-and-d813fe"
RIG_352066 = "3d-3d-model-generation-and-rigging-from-image-352066"
HOTSHOT = "hotshot-16-frames-agent-edit"


def _descriptor(scenario_id: str) -> dict:
    return json.loads((SCENARIOS_DIR / f"{scenario_id}.json").read_text(encoding="utf-8"))


def _write_response(output_dir: Path, response: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "response.json").write_text(
        json.dumps(response), encoding="utf-8"
    )


def _generic_clarify() -> dict:
    """The review's behavioral proof: a generic clarify without evidence."""
    return {
        "ok": True,
        "route": "clarify",
        "graph_unchanged": True,
        "outcome": {"kind": "clarify"},
        "message": "Please provide more detail.",
    }


def _errors(assessment: dict) -> list[str]:
    return [i["check"] for i in assessment["issues"] if i["severity"] == "error"]


def test_generic_clarify_fails_declared_no_candidate_scenario(
    tmp_path: Path,
) -> None:
    """DEEP-AUDIT-REVIEW-4-001 proof case: a generic clarify with no
    class-absence evidence must NOT pass an expected-no-candidate scenario."""
    scenario = _descriptor(D813FE)
    assert "expected_no_candidate_reason" in scenario["assessment"]
    _write_response(tmp_path, _generic_clarify())

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "fail", assessment["issues"]
    assert "expected_no_candidate_ungrounded" in _errors(assessment)


def test_grounded_class_absence_passes_declared_scenario(
    tmp_path: Path,
) -> None:
    """A response citing the declared absent class through the executor's
    structured surfaces passes per the declared refusal kind."""
    scenario = _descriptor(D813FE)
    _write_response(
        tmp_path,
        {
            "ok": True,
            "route": "requires_custom_nodes",
            "graph_unchanged": True,
            "outcome": {
                "kind": "requires_custom_nodes",
                "missing_classes": ["GroundingDINOBiABBEyeTip"],
            },
            "message": "GroundingDINO is not available in the authoring schema.",
            "report": {
                "authoring_blocker": {
                    "reason": "named_class_absent_from_schema",
                    "missing_runtime_classes": ["GroundingDINO"],
                    "message": "Which detector should be used instead?",
                },
            },
        },
    )

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "pass", assessment["issues"]
    grounded = [
        i for i in assessment["issues"]
        if i["check"] == "expected_no_candidate_grounded"
    ]
    assert len(grounded) == 1 and grounded[0]["severity"] == "info"


def test_cited_class_not_matching_declared_absence_fails(
    tmp_path: Path,
) -> None:
    """Structured evidence that names unrelated classes does not ground a
    declared named-class absence premise."""
    scenario = _descriptor(D813FE)
    response = _generic_clarify()
    response["route"] = "requires_custom_nodes"
    response["outcome"] = {
        "kind": "requires_custom_nodes",
        "missing_classes": ["SomeUnrelatedPackNode"],
    }
    _write_response(tmp_path, response)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "fail", assessment["issues"]
    ungrounded = [
        i for i in assessment["issues"]
        if i["check"] == "expected_no_candidate_ungrounded"
    ]
    assert len(ungrounded) == 1
    assert "do not match" in ungrounded[0]["detail"]


def test_wrong_refusal_kind_fails_declared_scenario(tmp_path: Path) -> None:
    """Even with grounding evidence present, an undeclared outcome kind
    cannot satisfy the refusal contract."""
    scenario = _descriptor(D813FE)
    response = _generic_clarify()
    response["route"] = "respond"
    response["outcome"] = {"kind": "noop"}
    response["no_candidate_reason"] = "no_changes"
    _write_response(tmp_path, response)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "fail", assessment["issues"]
    assert "expected_no_candidate_refusal_kind" in _errors(assessment)


def test_fabricated_edit_fails_declared_scenario(tmp_path: Path) -> None:
    """A declared expected-no-candidate scenario requires graph_unchanged;
    an edit (or unknown edit state) violates the refusal contract."""
    scenario = _descriptor(D813FE)
    _write_response(
        tmp_path,
        {
            "ok": True,
            "route": "adapt",
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
        },
    )

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "fail", assessment["issues"]
    assert "expected_no_candidate_graph_unchanged" in _errors(assessment)


def test_feature_absence_structural_label_passes_declared_scenario(
    tmp_path: Path,
) -> None:
    """Feature-absence premises (no class to cite) are grounded by the
    executor's structural no-candidate label instead."""
    scenario = _descriptor(RIG_352066)
    assert not scenario["assessment"].get(
        "expected_no_candidate_absent_classes"
    )
    response = _generic_clarify()
    response["message"] = (
        "No node controls knee orientation: TripoRigNode takes only a task id."
    )
    response["no_candidate_reason"] = "no_changes"
    _write_response(tmp_path, response)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "pass", assessment["issues"]


def test_hotshot_contract_grounds_on_family_token(tmp_path: Path) -> None:
    """The Hotshot fixture declares a family token; a cited Hotshot-prefixed
    class satisfies it."""
    scenario = _descriptor(HOTSHOT)
    response = _generic_clarify()
    response["route"] = "requires_custom_nodes"
    response["outcome"] = {
        "kind": "requires_custom_nodes",
        "missing_classes": ["HotshotXLImg2Img"],
    }
    _write_response(tmp_path, response)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "pass", assessment["issues"]


def test_flag_false_without_contract_still_scores_non_edit_runs(
    tmp_path: Path,
) -> None:
    """Regression guard: apply/expect_graph_changed false WITHOUT a declared
    contract keeps its existing behavior — a truthful non-edit answer still
    passes. The mechanism is strictly opt-in via expected_no_candidate_reason."""
    scenario = {
        "id": "synthetic-health-control",
        "apply": False,
        "assessment": {"expect_graph_changed": False},
    }
    _write_response(tmp_path, _generic_clarify())

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "pass", assessment["issues"]
    assert assessment["outcome_class"] == "non_edit_route_answered"


def test_obligations_derive_none_from_declared_contract() -> None:
    """Finding 001 (obligations half): for the three annotated scenarios,
    expected_change="none" derives from the declared refusal contract, which
    must be surfaced on the obligation with non-empty refusal kinds."""
    for scenario_id in (D813FE, RIG_352066, HOTSHOT):
        obligation = load_scenario_obligation(scenario_id)
        assert obligation is not None
        assert obligation.expected_change == "none"
        contract = obligation.expected_no_candidate
        assert contract is not None, scenario_id
        assert contract["reason"].strip(), scenario_id
        assert contract["refusal_kinds"], scenario_id


def test_contract_contradicting_edit_is_a_coverage_violation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A descriptor that declares expected-no-candidate while keeping edit
    expectations fails the fail-closed preflight."""
    descriptor = {
        "id": "synthetic-contradiction",
        "apply": True,
        "assessment": {
            "expect_graph_changed": True,
            "allow_safe_refusal_outcome_kinds": ["clarify"],
            "expected_no_candidate_reason": "deliberately contradictory",
        },
    }
    violations = _coverage_for(monkeypatch, tmp_path, descriptor)
    assert any("contradicts" in v for v in violations), violations


def test_contract_without_refusal_kinds_is_a_coverage_violation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Without declared refusal kinds the assessor would fail closed on every
    leg; the preflight must catch the broken annotation before paid calls."""
    descriptor = {
        "id": "synthetic-kindless",
        "apply": False,
        "assessment": {
            "expect_graph_changed": False,
            "allow_safe_refusal_outcome_kinds": [],
            "expected_no_candidate_reason": "absence premise without kinds",
        },
    }
    violations = _coverage_for(monkeypatch, tmp_path, descriptor)
    assert any("refusal_outcome_kinds" in v for v in violations), violations


def _coverage_for(monkeypatch, tmp_path: Path, descriptor: dict) -> list[str]:
    """Run validate_obligation_coverage against one synthetic descriptor."""
    from tests.live_agentic_harness import scenario_obligations as so

    path = tmp_path / f"{descriptor['id']}.json"
    path.write_text(json.dumps(descriptor), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"entries": [{"id": descriptor["id"]}]}), encoding="utf-8"
    )
    monkeypatch.setattr(
        so,
        "_authoritative_entries",
        lambda: {descriptor["id"]: {"path": str(path)}},
    )
    violations, _warnings = validate_obligation_coverage(
        manifest_path=manifest_path
    )
    return violations
