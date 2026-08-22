"""No-model contracts for the staged-versus-threaded comparison harness."""

from __future__ import annotations

import json
import threading
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


def test_validate_only_locks_r5_final_five_without_model_calls() -> None:
    path = (
        Path(__file__).parent
        / "live_agentic_harness"
        / "threaded_comparison_manifest_final5.json"
    )
    result = comparator.validate_only(path)

    assert result["ok"] is True
    assert result["model_calls"] == 0
    assert result["scenario_count"] == 5
    assert [item["id"] for item in result["locked_inputs"]] == [
        "audio-tts-narration-using-indextts-2",
        "image-image-editing-with-qwen-image",
        "live-graph-explanation-smoke",
        "multi-video-based-character-replacement-using",
        "speed-distillation-research",
    ]


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

    def fake_run(
        request: Any,
        *,
        entrypoint: str,
        scenario_id: str | None = None,
    ) -> FakeResult:
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
    assert "--concurrency" in help_text
    assert "two-step" not in help_text.lower()


def _seed_gated_schema_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Seed a disposable VIBECOMFY_OBJECT_INFO_CACHE_DIR with gated class evidence.

    G5-B4-MUST-006 made run_comparison's preflight fail-closed on
    IndexTTS/LayerMask schema provenance. These threaded tests exercise
    concurrency/isolation, not schema gating, so they provide a disposable
    authoritative cache that genuinely resolves the declared requirements
    (no bypass, no monkeypatch of _resolve_schema_locally).
    """
    cache_dir = tmp_path / "_gated_schema_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Classes the authoritative manifests declare as gated schema evidence.
    gated_requirements = [
        ("IndexTTSEngineNode", "ComfyUI-IndexTTS", {}),
        ("IndexTTSEmotionOptionsNode", "ComfyUI-IndexTTS", {"emotion_control": ["STRING", {}]}),
        ("LayerMask: LoadSegmentAnythingModels", "ComfyUI-LayerMask", {}),
        ("LayerMask: SegmentAnythingUltra V3", "ComfyUI-LayerMask", {}),
    ]
    index: dict[str, str] = {}
    files: dict[str, dict[str, dict]] = {}
    for class_type, pack, inputs in gated_requirements:
        filename = f"{pack}@test.json"
        index[class_type] = filename
        info: dict[str, object] = {
            "name": class_type,
            "display_name": class_type,
            "category": "test",
            "inputs": {"required": inputs} if inputs else {"required": {"dummy": ["STRING", {}]}},
            "outputs": [{"name": "OUTPUT", "type": "OUTPUT"}],
            "pack": pack,
            "pack_slug": pack.lower(),
            "object_info_widget_order": list(inputs.keys()) if inputs else ["dummy"],
        }
        files.setdefault(filename, {})[class_type] = info
    (cache_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    provenance: dict[str, object] = {
        "class_count": len(index),
        "packs": {
            filename: {
                "classes": len(classes),
                "locked_commit": "b" * 40,
                "pack": filename.split("@")[0],
                "repo": f"https://github.com/test/{filename.split('@')[0]}.git",
                "schema_sha256": "c" * 64,
            }
            for filename, classes in files.items()
        },
    }
    (cache_dir / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    for filename, classes in files.items():
        (cache_dir / filename).write_text(json.dumps(classes), encoding="utf-8")
    monkeypatch.setenv("VIBECOMFY_OBJECT_INFO_CACHE_DIR", str(cache_dir))
    return cache_dir


def _comparison_manifest_with_entries(tmp_path: Path, count: int = 5) -> Path:
    """Return a comparison manifest with ``count`` resolvable entries.

    G5-B4-MUST-006 made the gated IndexTTS/LayerMask scenarios require
    local authoritative schema evidence. To keep these no-model concurrency
    tests focused on their original intent (barrier concurrency, exception
    isolation, manifest-order reconstruction) the helper filters to
    entries whose obligations are fully resolvable at HEAD. The production
    fail-closed preflight itself is untouched — the manifest simply avoids
    triggering it so the concurrency contract can be exercised.
    """
    from tests.live_agentic_harness.scenario_obligations import SCHEMA_EVIDENCE_REQUIREMENTS

    manifest = json.loads(
        comparator.DEFAULT_COMPARISON_MANIFEST.read_text(encoding="utf-8")
    )
    gated_ids = set(SCHEMA_EVIDENCE_REQUIREMENTS.keys())
    filtered = [e for e in manifest["entries"] if e.get("id") not in gated_ids]
    manifest["entries"] = filtered[:count]
    path = tmp_path / f"comparison-{count}.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_concurrent_comparison_submits_all_legs_and_reconstructs_manifest_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _seed_gated_schema_cache(monkeypatch, tmp_path)
    manifest = _comparison_manifest_with_entries(tmp_path, count=5)
    entered = threading.Barrier(10)
    calls: list[tuple[str, str, int, str | None]] = []
    original_descriptors = {
        scenario_id: json.loads(
            (comparator.REPO / str(entry["path"])).read_text(encoding="utf-8")
        )
        for scenario_id, entry in comparator._authoritative_entries().items()
        if scenario_id in {
            str(item["id"])
            for item in json.loads(manifest.read_text(encoding="utf-8"))["entries"]
        }
    }

    monkeypatch.setattr(comparator, "validate_only", lambda _path=None: {"ok": True})

    def fake_run(
        scenario: dict[str, Any],
        *,
        mode: str,
        locked_input_sha256: str,
        output_base: Path,
        tag: str,
        transport: str | None,
    ) -> dict[str, Any]:
        calls.append((scenario["id"], mode, id(scenario), transport))
        # If legs were accidentally run sequentially, this barrier times out.
        entered.wait(timeout=3)
        scenario["mutated_by_worker"] = True
        return _summary(mode, locked_input_sha256)

    monkeypatch.setattr(comparator, "_run_mode", fake_run)
    payload = comparator.run_comparison(
        manifest,
        output_base=tmp_path / "out",
        transport="native",
        concurrency=10,
    )

    assert len(calls) == 10
    assert len({call[2] for call in calls}) == 10
    assert {call[3] for call in calls} == {"native"}
    expected_ids = [entry["id"] for entry in json.loads(manifest.read_text())["entries"]]
    assert [item["scenario_id"] for item in payload["scenarios"]] == expected_ids
    assert all("mutated_by_worker" not in descriptor for descriptor in original_descriptors.values())


def test_concurrent_comparison_isolates_leg_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _seed_gated_schema_cache(monkeypatch, tmp_path)
    manifest = _comparison_manifest_with_entries(tmp_path, count=5)
    monkeypatch.setattr(comparator, "validate_only", lambda _path=None: {"ok": True})
    calls: list[tuple[str, str]] = []

    def fake_run(
        scenario: dict[str, Any],
        *,
        mode: str,
        locked_input_sha256: str,
        output_base: Path,
        tag: str,
        transport: str | None,
    ) -> dict[str, Any]:
        calls.append((scenario["id"], mode))
        if scenario["id"] == json.loads(manifest.read_text())["entries"][0]["id"] and mode == "staged":
            raise RuntimeError("intentional leg failure")
        return _summary(mode, locked_input_sha256)

    monkeypatch.setattr(comparator, "_run_mode", fake_run)
    payload = comparator.run_comparison(
        manifest, output_base=tmp_path / "out", concurrency=10
    )

    assert len(calls) == 10
    assert len(payload["scenarios"]) == 5
    first = payload["scenarios"][0]
    assert first["staged"]["status"] == "runner_exception"
    assert first["staged"]["exception_type"] == "RuntimeError"
    assert all(item["threaded"]["status"] == "success" for item in payload["scenarios"])


def test_concurrent_comparison_rejects_explicit_session_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = _comparison_manifest_with_entries(tmp_path, count=1)
    descriptor_path = comparator.REPO / str(
        comparator._authoritative_entries()[
            json.loads(manifest.read_text())["entries"][0]["id"]
        ]["path"]
    )
    original_load = comparator._load_json

    def load_with_session(path: Path) -> dict[str, Any] | None:
        value = original_load(path)
        if path == descriptor_path and value is not None:
            value = dict(value)
            value["session_id"] = "shared-session"
        return value

    monkeypatch.setattr(comparator, "_load_json", load_with_session)
    monkeypatch.setattr(comparator, "validate_only", lambda _path=None: {"ok": True})

    with pytest.raises(comparator.ComparisonManifestError, match="session_id"):
        comparator.run_comparison(manifest, concurrency=2)


def test_concurrency_must_be_positive_and_parser_exposes_it() -> None:
    args = comparator._build_parser().parse_args(["--run", "--concurrency", "10"])
    assert args.concurrency == 10
    with pytest.raises(SystemExit):
        comparator._build_parser().parse_args(["--run", "--concurrency", "0"])
    with pytest.raises(comparator.ComparisonManifestError, match="positive integer"):
        comparator.run_comparison(concurrency=0)
