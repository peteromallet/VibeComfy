"""No-model contracts for the staged-versus-threaded comparison harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.live_agentic_harness import compare_pipeline_modes as comparator


def _summary(
    mode: str,
    lock: str,
    *,
    success: bool = True,
    failure_class: str | None = None,
    elapsed_s: float = 1.0,
    cost: float = 0.01,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    return {
        "pipeline_mode": mode,
        "status": "success" if success else "error",
        "ok": success,
        "output_dir": str(output_dir) if output_dir else None,
        "locked_input_sha256": lock,
        "elapsed_s": elapsed_s,
        "deepseek_usage": {"total_tokens": 10},
        "deepseek_est_cost_usd": cost,
        "failure_class": failure_class,
        "guard": {
            "live_agentic_success": success,
            "score_class": "pass" if success else "product_fail",
            "failure_class": failure_class,
        },
    }


def _write_response(output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "response.json").write_text(json.dumps(payload), encoding="utf-8")


def test_validate_only_locks_compact_lane_without_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.live_agentic_harness import adapter

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("validate-only must not invoke the live adapter")

    monkeypatch.setattr(adapter, "run_headless_scenario", forbidden)
    monkeypatch.setattr(
        comparator,
        "_adapter_wiring",
        lambda: {"status": "ready", "runnable": True, "selector": "pipeline_mode"},
    )
    result = comparator.validate_only()

    assert result["ok"] is True
    assert result["model_calls"] == 0
    assert result["scenario_count"] == 6
    assert result["modes"] == ["staged", "threaded"]
    assert len({item["id"] for item in result["locked_inputs"]}) == 6
    assert result["ir_projection"] == "tests.test_ir_laws.pi_edit"
    assert result["threaded_wiring"] == {
        "status": "ready",
        "runnable": True,
        "selector": "pipeline_mode",
    }


def test_validate_only_rejects_locked_input_drift(tmp_path: Path) -> None:
    manifest = json.loads(comparator.DEFAULT_COMPARISON_MANIFEST.read_text(encoding="utf-8"))
    manifest["entries"][0]["locked_input_sha256"] = "0" * 64
    path = tmp_path / "drifted.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(comparator.ComparisonManifestError, match="locked input drift"):
        comparator.validate_only(path)


def test_adapter_forwards_explicit_mode_without_model_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from tests.live_agentic_harness import adapter

    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy.agent import service

    seen: list[Any] = []

    class FakeResult:
        status = "success"
        ok = True
        response = {
            "deepseek_usage": {},
            "deepseek_est_cost_usd": 0.0,
            "model_attempts": [],
        }
        readiness: dict[str, Any] = {}
        error = None

    def fake_run(request: Any, *, entrypoint: str) -> FakeResult:
        seen.append(request)
        return FakeResult()

    monkeypatch.setattr(service, "run_headless", fake_run)
    result = adapter.run_headless_scenario(
        {"id": "scenario", "query": "inspect the graph"},
        output_base=tmp_path,
        pipeline_mode="threaded",
    )

    assert seen[0].pipeline_mode == "threaded"
    assert result["pipeline_mode"] == "threaded"


def test_canonical_delta_compares_typed_operations_not_reply_prose(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    base = {
        "accepted_batch": [
            {"id": "d1", "op": {"op": "set_mode", "target": ["", "uid-1"], "mode": 2}}
        ]
    }
    _write_response(first, {**base, "message": "I changed the graph."})
    _write_response(second, {**base, "message": "Completely different wording."})
    lock = "a" * 64

    comparison = comparator.compare_pair(
        "scenario",
        locked_input_sha256=lock,
        staged=_summary("staged", lock, output_dir=first),
        threaded=_summary("threaded", lock, output_dir=second),
    )

    assert comparison["delta"]["canonical_delta_equal"] is True
    assert "prose" not in comparison["delta"]
    assert "message_equal" not in comparison["delta"]

    _write_response(
        second,
        {
            "accepted_batch": [
                {
                    "id": "d1",
                    "op": {"op": "set_mode", "target": ["", "uid-1"], "mode": 4},
                }
            ]
        },
    )
    changed = comparator.compare_pair(
        "scenario",
        locked_input_sha256=lock,
        staged=_summary("staged", lock, output_dir=first),
        threaded=_summary("threaded", lock, output_dir=second),
    )
    assert changed["delta"]["canonical_delta_equal"] is False


def test_evidence_integrity_is_derived_from_typed_ledgers() -> None:
    response = {
        "report": {
            "executor": {
                "execute": {
                    "accepted_delta_ids": ["d1"],
                    "lens_fact_ids": ["f1"],
                    "evidence_ids": ["e1"],
                    "claim_refs": {
                        "delta_ids": ["d1"],
                        "lens_fact_ids": ["f1"],
                        "evidence_ids": ["missing"],
                    },
                    "claim_validation": {
                        "status": "valid",
                        "violations": [],
                    },
                }
            }
        }
    }

    integrity = comparator._evidence_integrity(response)
    assert integrity["delta_refs_valid"] is True
    assert integrity["lens_refs_valid"] is True
    assert integrity["evidence_refs_valid"] is False
    assert integrity["valid"] is False


def test_pair_outcome_and_failure_family_use_typed_evidence_only() -> None:
    lock = "b" * 64
    prose_only = _summary("staged", lock, success=False)
    prose_only["error"] = "provider timed out and the network failed"
    blocked = _summary("threaded", lock, success=False, failure_class="infra_timeout")
    passed = _summary("threaded", lock)

    assert comparator.is_infra_blocked(prose_only) is False
    assert comparator.is_infra_blocked(blocked) is True
    assert comparator.pair_outcome(prose_only, passed) == "threaded_only"
    assert comparator.pair_outcome(prose_only, blocked) == "blocked"


def test_comparison_reports_all_required_differential_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = "c" * 64
    monkeypatch.setattr(comparator, "_ir_projection_digest", lambda graph: "ir")
    staged = _summary("staged", lock, elapsed_s=2.0, cost=0.03)
    threaded = _summary("threaded", lock, elapsed_s=1.25, cost=0.02)
    result = comparator.compare_pair(
        "scenario", locked_input_sha256=lock, staged=staged, threaded=threaded
    )

    assert set(result["delta"]) == {
        "locked_input_equal",
        "ir_projection_equal",
        "canonical_delta_equal",
        "outcome_equal",
        "evidence_integrity_equal",
        "failure_family_equal",
        "latency_s",
        "cost_usd",
    }
    assert result["delta"]["locked_input_equal"] is True
    assert result["outcome"] == "both_pass"
    assert result["delta"]["latency_s"]["threaded_minus_staged"] == -0.75
    assert result["delta"]["cost_usd"]["threaded_minus_staged"] == -0.01


def test_latency_and_cost_are_read_from_typed_metrics_artifacts(tmp_path: Path) -> None:
    lock = "d" * 64
    staged_dir = tmp_path / "staged"
    threaded_dir = tmp_path / "threaded"
    for directory, elapsed, cost in (
        (staged_dir, 2.0, 0.03),
        (threaded_dir, 1.25, 0.02),
    ):
        _write_response(directory, {})
        (directory / "comparison_metrics.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "pipeline_mode": directory.name,
                    "locked_input_sha256": lock,
                    "elapsed_s": elapsed,
                    "deepseek_usage": {"total_tokens": 10},
                    "deepseek_est_cost_usd": cost,
                }
            ),
            encoding="utf-8",
        )

    result = comparator.compare_pair(
        "scenario",
        locked_input_sha256=lock,
        staged=_summary("staged", lock, elapsed_s=99.0, cost=9.0, output_dir=staged_dir),
        threaded=_summary("threaded", lock, elapsed_s=99.0, cost=9.0, output_dir=threaded_dir),
    )

    assert result["delta"]["latency_s"]["threaded_minus_staged"] == -0.75
    assert result["delta"]["cost_usd"]["threaded_minus_staged"] == -0.01


def test_live_run_passes_identical_copies_to_explicit_mode_wiring(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from tests.live_agentic_harness import adapter

    canonical = json.loads(comparator.DEFAULT_COMPARISON_MANIFEST.read_text(encoding="utf-8"))
    canonical["entries"] = canonical["entries"][:1]
    manifest = tmp_path / "one.json"
    manifest.write_text(json.dumps(canonical), encoding="utf-8")
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_run(
        scenario: dict[str, Any],
        *,
        output_base: Path,
        tag: str,
        transport: str | None,
        pipeline_mode: str,
    ) -> dict[str, Any]:
        calls.append((pipeline_mode, scenario))
        return {
            "scenario_id": scenario["id"],
            "pipeline_mode": pipeline_mode,
            "status": "success",
            "ok": True,
            "output_dir": str(output_base / tag / scenario["id"]),
            "deepseek_usage": {},
            "deepseek_est_cost_usd": 0.0,
        }

    monkeypatch.setattr(adapter, "run_headless_scenario", fake_run)
    payload = comparator.run_comparison(manifest, output_base=tmp_path / "out")

    assert [mode for mode, _ in calls] == ["staged", "threaded"]
    assert calls[0][1] == calls[1][1]
    assert payload["aggregate"]["all_inputs_locked_equal"] is True


def test_cli_uses_threaded_terminology_only() -> None:
    parser = comparator._build_parser()
    help_text = parser.format_help()
    assert "--validate-only" in help_text
    assert "--run" in help_text
    assert "two-step" not in help_text.lower()
