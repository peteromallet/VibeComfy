from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness import assessor, compare_pipeline_modes, guard, reassess, runner
from tests.live_agentic_harness.judge_config import (
    JudgeConfig,
    JudgeReadinessError,
    require_judge_readiness,
    resolve_judge_config,
)


def test_judge_config_rejects_blank_values() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        resolve_judge_config(" ", "gpt-5.6-luna")
    with pytest.raises(ValueError, match="non-empty"):
        resolve_judge_config("openai-codex", " ")


def test_judge_readiness_uses_public_provider_and_records_requested_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import provider

    seen: list[tuple[str | None, str | None]] = []

    def ready(*, route=None, model=None):
        seen.append((route, model))
        return {"ready": True, "route": route, "model": model, "provider": "arnold"}

    monkeypatch.setattr(provider, "readiness", ready)
    receipt = require_judge_readiness(JudgeConfig("openai-codex", "gpt-5.6-luna"))
    assert seen == [("openai-codex", "gpt-5.6-luna")]
    assert receipt["requested_route"] == "openai-codex"
    assert receipt["requested_model"] == "gpt-5.6-luna"


def test_comparison_preflight_failure_happens_before_validation_or_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def unavailable(_config):
        events.append("preflight")
        raise JudgeReadinessError("no judge")

    monkeypatch.setattr(compare_pipeline_modes, "require_judge_readiness", unavailable)
    monkeypatch.setattr(
        compare_pipeline_modes,
        "validate_only",
        lambda *_args, **_kwargs: events.append("validate"),
    )
    with pytest.raises(compare_pipeline_modes.ComparisonManifestError, match="no judge"):
        compare_pipeline_modes.run_comparison()
    assert events == ["preflight"]


def test_runner_preflight_failure_happens_before_product_adapter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"id": "s", "query": "inspect"}), encoding="utf-8")
    called: list[str] = []

    def unavailable(_config):
        raise JudgeReadinessError("judge unavailable")

    monkeypatch.setattr(runner, "require_judge_readiness", unavailable)
    from tests.live_agentic_harness import adapter

    monkeypatch.setattr(
        adapter,
        "run_headless_scenario",
        lambda *_args, **_kwargs: called.append("product"),
    )
    with pytest.raises(JudgeReadinessError, match="judge unavailable"):
        runner.run_single(str(scenario), "tag", tmp_path / "out", None)
    assert called == []


def test_process_leg_spec_persists_complete_resolved_judge_pair(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.json"
    compare_pipeline_modes._write_leg_spec(
        spec_path,
        scenario={"id": "s"},
        mode="staged",
        locked_input_sha256="a" * 64,
        output_base=tmp_path / "out",
        tag="tag",
        transport="native",
        judge_route="openai-codex",
        judge_model="gpt-5.6-luna",
        attempt_identity="attempt-2",
    )
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["judge_config"] == {
        "route": "openai-codex",
        "model": "gpt-5.6-luna",
    }
    assert "judge_route" not in spec and "judge_model" not in spec


def test_assessor_judge_receipt_records_requested_pair_for_early_result() -> None:
    issues: list[dict] = []
    results: list[dict] = []
    assessor._record_judge_result(
        issues=issues,
        judge_results=results,
        check="intent_judge",
        judge_name="edit_intent",
        verdict={"pass_": None, "error": "withheld_accepted_batch"},
        requested_route="openai-codex",
        requested_model="gpt-5.6-luna",
    )
    assert results[0]["metadata"] == {
        "requested_route": "openai-codex",
        "requested_model": "gpt-5.6-luna",
    }


def test_alternate_assessment_publication_does_not_touch_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    original = source / "assessment.json"
    original.write_text('{"old":true}\n', encoding="utf-8")
    destination = tmp_path / "reassessment" / "assessment.json"
    assessor._publish_assessment(
        source,
        {"verdict": "pass", "passed": True},
        assessment_path=destination,
    )
    assert original.read_text(encoding="utf-8") == '{"old":true}\n'
    assert json.loads(destination.read_text(encoding="utf-8"))["verdict"] == "pass"


def test_reassessment_collects_final_comparison_legs_not_raw_attempts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    staged = source / "staged" / "tag" / "s"
    threaded = source / "threaded" / "tag" / "s"
    staged.mkdir(parents=True)
    threaded.mkdir(parents=True)
    (staged / "response.json").write_text("{}", encoding="utf-8")
    (threaded / "response.json").write_text("{}", encoding="utf-8")
    (source / "_legs").mkdir()
    (source / "_legs" / "result_9999_stale.json").write_text("{}", encoding="utf-8")
    (source / "comparison.json").write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "scenario_id": "s",
                        "staged": {"output_dir": str(staged)},
                        "threaded": {"output_dir": str(threaded)},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"entries": [{"id": "s"}]}), encoding="utf-8")
    monkeypatch.setattr(reassess, "validate_only", lambda _path: {"ok": True})
    monkeypatch.setattr(
        reassess,
        "_authoritative_entries",
        lambda: {"s": {"path": "tests/live_agentic_harness/scenarios/s.json"}},
    )
    legs = reassess._collect_legs(source, manifest, set())
    assert [(leg["scenario_id"], leg["mode"]) for leg in legs] == [
        ("s", "staged"),
        ("s", "threaded"),
    ]


def test_reassess_leg_uses_guard_and_separate_assessment_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    descriptor = tmp_path / "scenario.json"
    descriptor.write_text(json.dumps({"id": "s", "query": "edit"}), encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    source_assessment = source / "assessment.json"
    source_assessment.write_text('{"old":true}\n', encoding="utf-8")

    def fake_guard(output_dir, scenario, **kwargs):
        assert Path(output_dir) == source
        target = Path(kwargs["assessment_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"verdict":"pass"}\n', encoding="utf-8")
        assessment = {
            "judge_config": {
                "route": kwargs["judge_route"],
                "model": kwargs["judge_model"],
            },
            "judge_results": [],
        }
        return {
            "verdict": "pass",
            "score_class": "pass",
            "live_agentic_success": True,
            "assessment": assessment,
        }

    monkeypatch.setattr(guard, "guard_output_dir", fake_guard)
    result = reassess._reassess_leg(
        {
            "index": 0,
            "scenario_id": "s",
            "mode": "staged",
            "output_dir": str(source),
            "descriptor_path": str(descriptor),
        },
        output_base=str(tmp_path / "out"),
        judge_route="openai-codex",
        judge_model="gpt-5.6-luna",
    )
    assert result["live_agentic_success"] is True
    assert source_assessment.read_text(encoding="utf-8") == '{"old":true}\n'
    assert Path(result["assessment_path"]).is_file()
