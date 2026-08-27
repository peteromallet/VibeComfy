"""T5.3 scenario obligations and fail-closed preflight."""

from __future__ import annotations

import json
from collections import OrderedDict
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
    assert {"Sad", "Disgusted", "Calm"} <= set(emotion_req.get("required_field_evidence", ()))
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


def test_preflight_fails_closed_for_unproven_final50_and_passes_final5() -> None:
    """OQ2+new50: FINAL50's 6 previously-blocked gated classes now have honest
    on_demand captures and declarations, so BOTH final50 and final5 pass
    the preflight (UNPROVEN is
    empty and the enforcement gate remains)."""
    result50 = so.preflight_scenario_obligations(FINAL50, require_schema_resolution=False)
    assert result50["ok"] is True
    assert result50["schema_resolution_enforced"] is True
    assert result50["violations"] == []
    result5 = so.preflight_scenario_obligations(FINAL5, require_schema_resolution=False)
    assert result5["ok"] is True
    assert result5["schema_resolution_enforced"] is True
    assert result5["violations"] == []
    layermask_rows = [
        per_class
        for per_class in result5["resolution"].values()
        if "LayerMask: SegmentAnythingUltra V3" in per_class
    ]
    assert layermask_rows
    assert layermask_rows[0]["LayerMask: SegmentAnythingUltra V3"] is True
    # No residual gap - all gated classes declared.
    assert so.UNPROVEN_PROVIDER_CLASSES == {}


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


# ---------------------------------------------------------------------------
# Batch D — on-demand tiers accepted as themselves; runtime_only strict flag.
# All cases are local-only: tmp caches seeded via ``persist_on_demand_pack``,
# no network, no OnDemandInstallSchemaProvider.
# ---------------------------------------------------------------------------

_COMMIT = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
_SHA7 = _COMMIT[:7]
_AUDIO_SID = "audio-tts-narration-using-indextts-2"


def _extract_entry(class_name: str, *, pack: str = "Pack") -> "OrderedDict[str, object]":
    """A normalize_entry-shaped extract result for one synthetic class."""
    return OrderedDict(
        (
            ("pack", pack),
            ("pack_version", "1.2.3"),
            ("python_module", f"custom_nodes.{pack}.nodes"),
            ("category", "pack"),
            ("name", class_name),
            ("display_name", class_name),
            ("description", ""),
            ("inputs", {"required": {"value": ["INT", {"default": 1}]}}),
            ("input_order", {"required": ["value"]}),
            ("input_order_all", ["value"]),
            ("object_info_widget_order", [None]),
            ("outputs", [{"type": "IMAGE", "name": "IMAGE", "is_list": False}]),
            ("function", class_name.lower()),
        )
    )


def _persist(cache_root: Path, entries: dict, rung: str = "ast"):
    from vibecomfy.schema.ensure_capture import persist_on_demand_pack

    return persist_on_demand_pack(
        pack_slug="Pack",
        registry_pack_version="1.2.3",
        repo="https://github.com/example/Pack",
        locked_commit=_COMMIT,
        extraction_rung=rung,
        entries=entries,
        cache_dir=cache_root,
    )


def _ondemand_req(source: str = "on_demand_static", cls: str = "GapNode") -> dict:
    return {
        "class_type": cls,
        "pack": "Pack",
        "source": source,
        "required_field_evidence": (),
        "required_inputs": (),
        "required_widgets": (),
        "required_outputs": (),
    }


def _synthetic_obligation(requirement: dict) -> so.ScenarioObligation:
    """One declared requirement on a real scenario id (so the coverage pass
    can load its descriptor); requires_edit=False keeps undeclared gated-
    class checks out of the way."""
    return so.ScenarioObligation(
        scenario_id=_AUDIO_SID,
        purpose="batch d preflight payload",
        expected_change="edit",
        invariants=(),
        research_requirements=(),
        custom_node_classes=(),
        schema_evidence_requirements=(requirement,),
        prompt_tool_contract={},
        requires_edit=False,
    )


def _tmp_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"entries": [{"id": _AUDIO_SID}]}), encoding="utf-8"
    )
    return path


def test_ondemand_declared_and_matched_resolves_with_tier(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    persisted = _persist(cache, {"GapNode": _extract_entry("GapNode")})
    assert persisted.written_classes == ["GapNode"]
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [cache])
    req = _ondemand_req()

    resolved, failures = so._resolve_schema_locally(req)
    assert resolved, failures

    monkeypatch.setattr(
        so, "load_scenario_obligation", lambda sid: _synthetic_obligation(req)
    )
    payload = so.preflight_scenario_obligations(_tmp_manifest(tmp_path))
    assert payload["ok"] is True
    sid = _AUDIO_SID
    assert payload["resolution"][sid]["GapNode"] is True
    tier = payload["resolution_tiers"][sid]["GapNode"]
    assert tier["source_kind"] == "on_demand_static"  # the CACHE stamp
    assert tier["locked_commit"] == _COMMIT
    assert tier["extraction_rung"] == "ast"


def test_ondemand_capture_cannot_masquerade_as_authoritative(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    _persist(cache, {"GapNode": _extract_entry("GapNode")})
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [cache])

    resolved, failures = so._resolve_schema_locally(
        _ondemand_req(source="authoritative_object_info")
    )
    assert not resolved
    joined = "; ".join(failures)
    assert "on_demand_static" in joined
    assert "not a runtime-family object_info dump" in joined

    # No upgrades either: an import-tier capture does not satisfy a static
    # declaration.
    fresh = tmp_path / "fresh"
    _persist(fresh, {"GapNode": _extract_entry("GapNode")}, rung="import")
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [fresh])
    resolved, failures = so._resolve_schema_locally(_ondemand_req())
    assert not resolved
    assert "on_demand_import" in "; ".join(failures)

    # An on-demand-shaped filename never satisfies authoritative, even if the
    # pack JSON stamp claims a runtime kind.
    lying = tmp_path / "lying"
    _seed_cache_file(
        lying,
        "Pack@on_demand_static-deadbee.json",
        dict(_extract_entry("GapNode"), source_kind="runtime_object_info"),
        cls="GapNode",
    )
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [lying])
    resolved, failures = so._resolve_schema_locally(
        _ondemand_req(source="authoritative_object_info")
    )
    assert not resolved
    assert any("not a runtime-family" in f for f in failures)


def _seed_cache_file(cache: Path, filename: str, entry: dict, cls: str = "Stubbed") -> None:
    """Hand-write a one-class indexed+attested cache file (any shape)."""
    cache.mkdir(parents=True, exist_ok=True)
    (cache / filename).write_text(json.dumps({cls: entry}), encoding="utf-8")
    (cache / "index.json").write_text(
        json.dumps({cls: filename}), encoding="utf-8"
    )
    provenance = {
        "class_count": 1,
        "packs": {
            filename: {
                "pack": "Pack",
                "repo": "https://github.com/example/Pack",
                "locked_commit": _COMMIT,
                "schema_sha256": "d" * 64,
            }
        },
    }
    (cache / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")


def test_stub_shaped_captures_fail_even_when_indexed_and_attested(tmp_path, monkeypatch):
    req = _ondemand_req(source="authoritative_object_info", cls="Stubbed")

    # (a) @stub.json suffix: the provider index drops the row outright.
    stub_suffix = tmp_path / "stub-suffix"
    _seed_cache_file(stub_suffix, "Pack@stub.json", dict(_extract_entry("Stubbed")))
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [stub_suffix])
    resolved, failures = so._resolve_schema_locally(req)
    assert not resolved

    # (b) non-@stub.json filename whose pack JSON stamps workflow_json_stub —
    # survives the index suffix filter, must STILL fail explicitly.
    stamped = tmp_path / "stamped"
    entry = dict(_extract_entry("Stubbed"), source_kind="workflow_json_stub")
    _seed_cache_file(stamped, "Pack@weird.json", entry)
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [stamped])
    resolved, failures = so._resolve_schema_locally(req)
    assert not resolved
    assert any("stub" in f.lower() for f in failures)


def test_runtime_only_rejects_matched_ondemand(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    _persist(cache, {"GapNode": _extract_entry("GapNode")})
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [cache])
    req = _ondemand_req()

    resolved, failures = so._resolve_schema_locally(req, runtime_only=True)
    assert not resolved
    assert any(so.RUNTIME_ONLY_ENV_VAR in f for f in failures)
    # The strict rejection never suggests schemas ensure (it mints on-demand).
    assert not any("schemas ensure" in f for f in failures)

    # Env var + runtime_only=None behaves identically at the preflight level.
    monkeypatch.setattr(
        so, "load_scenario_obligation", lambda sid: _synthetic_obligation(req)
    )
    manifest = _tmp_manifest(tmp_path)
    monkeypatch.setenv(so.RUNTIME_ONLY_ENV_VAR, "1")
    with pytest.raises(so.ScenarioObligationError) as excinfo:
        so.preflight_scenario_obligations(manifest)
    message = str(excinfo.value)
    assert so.RUNTIME_ONLY_ENV_VAR in message
    assert "schemas ensure" not in message

    # Explicit False wins over the env var.
    payload = so.preflight_scenario_obligations(manifest, runtime_only=False)
    assert payload["ok"] is True


def test_final5_legacy_pins_record_resolution_tiers() -> None:
    result = so.preflight_scenario_obligations(FINAL5)
    assert result["ok"] is True
    tiers = result["resolution_tiers"]
    assert isinstance(tiers, dict)
    hits = [
        tier["LayerMask: SegmentAnythingUltra V3"]
        for tier in tiers.values()
        if "LayerMask: SegmentAnythingUltra V3" in tier
    ]
    assert hits and all(hit["locked_commit"] for hit in hits)


def test_ondemand_miss_names_ensure_command(tmp_path, monkeypatch):
    monkeypatch.setattr(so, "_authoritative_cache_roots", lambda: [tmp_path / "empty"])
    req = _ondemand_req()
    monkeypatch.setattr(
        so, "load_scenario_obligation", lambda sid: _synthetic_obligation(req)
    )
    manifest = _tmp_manifest(tmp_path)
    with pytest.raises(so.ScenarioObligationError) as excinfo:
        so.preflight_scenario_obligations(manifest)
    assert f"vibecomfy schemas ensure --manifest {manifest}" in str(excinfo.value)


def test_on_demand_runtime_declaration_is_invalid(tmp_path, monkeypatch):
    # Fails before any cache lookup: even an empty root set rejects it.
    monkeypatch.setattr(
        so, "_authoritative_cache_roots", lambda: [tmp_path / "nope"]
    )
    req = _ondemand_req(source="on_demand_runtime")
    resolved, failures = so._resolve_schema_locally(req)
    assert not resolved
    assert any("on_demand_runtime" in f for f in failures)

    # And it is a declaration-level coverage violation too.
    monkeypatch.setattr(
        so, "load_scenario_obligation", lambda sid: _synthetic_obligation(req)
    )
    violations, _warnings = so.validate_obligation_coverage(_tmp_manifest(tmp_path))
    assert any("on_demand_runtime" in v for v in violations)
