"""T5.3 scenario obligations and fail-closed preflight."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness import scenario_obligations as so
from tests.live_agentic_harness.compare_pipeline_modes import (
    DEFAULT_COMPARISON_MANIFEST,
    DEFAULT_OUTPUT_BASE,
    _authoritative_entries,
)

FINAL50 = (
    Path(__file__).parent / "live_agentic_harness/threaded_comparison_manifest_final50.json"
)
FINAL5 = (
    Path(__file__).parent / "live_agentic_harness/threaded_comparison_manifest_final5.json"
)


def test_every_final50_scenario_has_complete_obligations() -> None:
    manifest = json.loads(FINAL50.read_text(encoding="utf-8"))
    ids = [str(entry["id"]) for entry in manifest["entries"]]
    assert len(ids) == 50
    for scenario_id in ids:
        obligation = so.load_scenario_obligation(scenario_id)
        assert obligation is not None, scenario_id
        assert obligation.purpose, scenario_id
        assert obligation.expected_change in {
            "edit",
            "none",
            "research_answer",
            "inspect_answer",
        }
        assert "accepted_batch_is_sole_mutation_authority" in obligation.invariants
        assert obligation.prompt_tool_contract["modes"] == ["staged", "threaded"]
        assert obligation.admissible_infra_failures == ("infra_timeout", "infra_empty_response")


def test_final5_core_is_subset_with_identical_obligations() -> None:
    m50 = json.loads(FINAL50.read_text(encoding="utf-8"))
    m5 = json.loads(FINAL5.read_text(encoding="utf-8"))
    core = [str(e["id"]) for e in m5["entries"]]
    head50 = [str(e["id"]) for e in m50["entries"]][: len(core)]
    assert core == head50  # r5-comparable core stays entries 1-5


def test_audio_and_multivideo_declare_exact_schema_evidence() -> None:
    audio = so.load_scenario_obligation("audio-tts-narration-using-indextts-2")
    multivideo = so.load_scenario_obligation(
        "multi-video-based-character-replacement-using"
    )
    audio_classes = {req["class_type"] for req in audio.schema_evidence_requirements}
    assert {"IndexTTSEngineNode", "IndexTTSEmotionOptionsNode"} <= audio_classes
    emotion_req = next(
        r
        for r in audio.schema_evidence_requirements
        if r["class_type"] == "IndexTTSEmotionOptionsNode"
    )
    assert emotion_req["pack"] == "ComfyUI-IndexTTS"
    assert "emotion_control" in emotion_req.get("required_field_evidence", ())
    video_classes = {req["class_type"] for req in multivideo.schema_evidence_requirements}
    assert {
        "LayerMask: LoadSegmentAnythingModels",
        "LayerMask: SegmentAnythingUltra V3",
    } <= video_classes
    for req in multivideo.schema_evidence_requirements:
        assert req["pack"] == "ComfyUI_LayerStyle_Advance"


def test_multivideo_requirements_resolve_against_repointed_snapshot() -> None:
    """R1BR-001 regression: the pinned LayerMask snapshot is owned by
    ComfyUI_LayerStyle_Advance, so both multi-video requirements must resolve
    POSITIVELY from local authoritative evidence (the stale 'ComfyUI-LayerMask'
    alias failed the exact pack comparison and blocked paid preflight)."""
    obligation = so.load_scenario_obligation(
        "multi-video-based-character-replacement-using"
    )
    resolutions = {
        str(req["class_type"]): so._resolve_schema_locally(req)
        for req in obligation.schema_evidence_requirements
    }
    assert set(resolutions) == {
        "LayerMask: LoadSegmentAnythingModels",
        "LayerMask: SegmentAnythingUltra V3",
    }
    for class_type, (resolved, failures) in resolutions.items():
        assert resolved, f"{class_type}: {failures}"


def test_preflight_schema_resolution_succeeds_with_pinned_snapshot() -> None:
    """The shipped authoritative cache carries exact evidence for every gated
    class, so the paid-call preflight passes with schema resolution enforced."""
    result = so.preflight_scenario_obligations(FINAL5, require_schema_resolution=True)
    assert result["ok"] is True
    assert result["schema_resolution_enforced"] is True
    assert result["resolution"]["multi-video-based-character-replacement-using"] == {
        "LayerMask: LoadSegmentAnythingModels": True,
        "LayerMask: SegmentAnythingUltra V3": True,
    }


def test_undeclared_gated_class_is_a_coverage_violation(monkeypatch) -> None:
    monkeypatch.setitem(so.SCHEMA_EVIDENCE_REQUIREMENTS, "audio-tts-narration-using-indextts-2", ())
    violations, _warnings = so.validate_obligation_coverage(FINAL5)
    assert any(
        "IndexTTSEngineNode" in v and "no exact" in v for v in violations
    ), violations
    with pytest.raises(so.ScenarioObligationError, match="IndexTTSEngineNode"):
        so.preflight_scenario_obligations(FINAL5)


def test_incomplete_requirement_missing_pack_is_violation(monkeypatch) -> None:
    monkeypatch.setitem(
        so.SCHEMA_EVIDENCE_REQUIREMENTS,
        "audio-tts-narration-using-indextts-2",
        ({"class_type": "IndexTTSEngineNode", "source": "authoritative_object_info"},),
    )
    violations, _warnings = so.validate_obligation_coverage(FINAL5)
    assert any(
        "IndexTTSEngineNode" in v and "pack" in v for v in violations
    ), violations


def test_safe_refusal_cannot_satisfy_edit_scenarios() -> None:
    for scenario_id, entry in _authoritative_entries().items():
        obligation = so.load_scenario_obligation(scenario_id)
        if obligation is not None and obligation.requires_edit:
            assert obligation.safe_refusal_cannot_satisfy is True


def test_descriptor_granting_safe_refusal_on_edit_scenario_fails_closed(
    monkeypatch,
) -> None:
    real_load = so._load_json

    def forged_load(path):
        value = real_load(path)
        if isinstance(value, dict) and value.get("id") == "audio-tts-narration-using-indextts-2":
            forged = json.loads(json.dumps(value))
            forged.setdefault("assessment", {})[
                "allow_safe_refusal_outcome_kinds"
            ] = ["clarify"]
            return forged
        return value

    monkeypatch.setattr(so, "_load_json", forged_load)
    violations, warnings = so.validate_obligation_coverage(FINAL5)
    assert not any("allow_safe_refusal_outcome_kinds" in v for v in violations)
    assert any(
        "allow_safe_refusal_outcome_kinds" in w for w in warnings
    ), warnings


def test_preflight_declaration_level_passes_for_locked_manifests() -> None:
    result = so.preflight_scenario_obligations(FINAL50, require_schema_resolution=False)
    assert result["ok"] is True
    assert result["schema_resolution_enforced"] is False
    assert result["violations"] == []
    result5 = so.preflight_scenario_obligations(FINAL5, require_schema_resolution=False)
    assert result5["ok"] is True


def test_preflight_schema_resolution_fails_closed_without_local_evidence(
    tmp_path, monkeypatch
) -> None:
    """No local authoritative source carries the gated classes here, so the
    paid-call gate MUST refuse (r5 failure #2/#3 discovery before spend).
    R1BR-001: the shipped repo cache is itself an authoritative root now
    (pinned ComfyUI_LayerStyle_Advance snapshot), so the no-evidence world
    isolates every authoritative root away from it."""
    empty_root = tmp_path / "empty"
    monkeypatch.setattr(
        so, "_authoritative_cache_roots", lambda: [empty_root]
    )
    with pytest.raises(so.ScenarioObligationError) as excinfo:
        so.preflight_scenario_obligations(FINAL5, require_schema_resolution=True)
    message = str(excinfo.value)
    assert "IndexTTSEmotionOptionsNode" in message
    assert "LayerMask: SegmentAnythingUltra V3" in message


def test_env_var_enables_schema_resolution(monkeypatch) -> None:
    monkeypatch.setenv(so.SCHEMA_RESOLUTION_ENV_VAR, "1")
    # R1BR-001: exclude the shipped authoritative cache so the gate still has
    # nothing local to resolve against and refuses paid calls fail-closed.
    monkeypatch.setattr(
        so,
        "_authoritative_cache_roots",
        lambda: [Path("/tmp/b4-impl/no-such-cache")],
    )
    with pytest.raises(so.ScenarioObligationError):
        so.preflight_scenario_obligations(FINAL5)


def test_bare_untyped_non_edit_obligation_is_a_coverage_violation() -> None:
    """ADJUDICATION-4 ruling 1.1f: an edit-kind scenario that merely sets
    apply=false + expect_graph_changed=false — with no explicit non-edit lane
    (health_control / answer rubric / answer_only / executed research) and no
    declared expected-no-candidate contract — is an invalid untyped non-edit
    obligation. The PURE descriptor validator flags it; no manifest or
    authoritative-entry coupling, no monkeypatching."""
    descriptor = {
        "id": "synthetic-bare-non-edit",
        "apply": False,
        "assessment": {"expect_graph_changed": False},
    }
    violations = so.descriptor_contract_violations(descriptor)
    assert any("bare apply=false" in v for v in violations), violations

    # The same bare flags on an explicitly typed lane stay legal.
    typed_lane = dict(
        descriptor,
        classification={"kind": "health_control"},
    )
    assert so.descriptor_contract_violations(typed_lane) == ()
    rubric_lane = dict(descriptor, answer_rubric={"judge": "semantic_answer"})
    assert so.descriptor_contract_violations(rubric_lane) == ()
    contract_lane = dict(
        descriptor,
        assessment={
            "expect_graph_changed": False,
            "allow_safe_refusal_outcome_kinds": ["requires_custom_nodes"],
            "expected_no_candidate_reason": "declared absence premise",
            "expected_no_candidate_absent_classes": ["SomeAbsentClass"],
        },
    )
    assert so.descriptor_contract_violations(contract_lane) == ()


def test_validate_only_reports_zero_obligation_violations() -> None:
    from tests.live_agentic_harness.compare_pipeline_modes import validate_only

    payload = validate_only(DEFAULT_COMPARISON_MANIFEST)
    assert payload["obligation_violations"] == []
    assert payload["obligation_preflight"] == "declaration_level"


def test_run_comparison_preflight_runs_before_legs(tmp_path, monkeypatch) -> None:
    """The obligation preflight fires before any leg execution."""
    order: list[str] = []

    def fake_validate_only(_path=None):
        order.append("validate")
        return {"ok": True}

    def exploding_preflight(_path, **kwargs):
        order.append("preflight")
        raise so.ScenarioObligationError("injected")

    def exploding_run_mode(*args, **kwargs):
        raise AssertionError("legs must not start after preflight failure")

    monkeypatch.setattr(
        "tests.live_agentic_harness.compare_pipeline_modes.validate_only",
        fake_validate_only,
    )
    monkeypatch.setattr(so, "preflight_scenario_obligations", exploding_preflight)
    monkeypatch.setattr(
        "tests.live_agentic_harness.compare_pipeline_modes._run_mode",
        exploding_run_mode,
    )
    from tests.live_agentic_harness.compare_pipeline_modes import run_comparison

    with pytest.raises(so.ScenarioObligationError, match="injected"):
        run_comparison(FINAL5, output_base=tmp_path / "out")
    assert order == ["validate", "preflight"]
