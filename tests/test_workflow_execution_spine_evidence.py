from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_workflow_execution_spine_evidence.py"
spec = importlib.util.spec_from_file_location("vcspine_validator", VALIDATOR_PATH)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def _manifest() -> dict:
    return {
        "schema_version": "1",
        "final_five": dict(validator.FINAL_FIVE),
        "gates": [], "shards": [], "live_runs": [], "findings": [],
        "tasks": [
            {"task_id": "T0.0", "label": "T0.0 [HARD] source", "model_route": "codex:gpt-5.6-luna"},
            {"task_id": "T0.1", "label": "T0.1 [HARD] freeze", "model_route": "codex:gpt-5.6-luna"},
            {"task_id": "T0.3", "label": "T0.3 [HARD] wrapper", "model_route": "codex:gpt-5.6-luna"},
        ],
    }


def _error(manifest: dict, check: str) -> str:
    with pytest.raises(validator.EvidenceValidationError) as caught:
        validator.validate_manifest(manifest, ROOT / "manifest.json")
    assert caught.value.error_type == check
    return str(caught.value)


def test_dependency_order_rejects_reversed_cards() -> None:
    manifest = _manifest()
    manifest["tasks"] = [manifest["tasks"][1], manifest["tasks"][0], manifest["tasks"][2]]
    _error(manifest, "DEPENDENCY_ORDER")


def test_model_routing_rejects_xhard_on_luna() -> None:
    manifest = _manifest()
    manifest["tasks"][0]["label"] = "T0.0 [XHARD] source"
    _error(manifest, "MODEL_ROUTING")


def test_reviewer_independence_rejects_self_review() -> None:
    manifest = _manifest()
    manifest["tasks"].append({
        "task_id": "T0.2", "label": "T0.2 [XHARD-REVIEW] contract", "model_route": "grok-4.6",
        "role": "reviewer", "reviewer_agent_id": "agent-a", "implementer_agent_id": "agent-a",
    })
    _error(manifest, "REVIEWER_INDEPENDENCE")


def test_must_finding_requires_closed_revision_chain() -> None:
    manifest = _manifest()
    manifest["findings"] = [{"finding_id": "F1", "severity": "must", "classification": "XHARD"}]
    _error(manifest, "FINDING_CHAIN")


def test_final_five_identity_is_locked() -> None:
    manifest = _manifest()
    manifest["final_five"]["speed-distillation-research"] = "0" * 64
    _error(manifest, "FINAL_FIVE_INTEGRITY")


def _authoritative_run(count: int = 100, mode: str = "50x2", *, duplicate: bool = False, keyless: bool = False) -> dict:
    receipts: list[dict] = []
    for i in range(count):
        if keyless:
            receipts.append({})
        elif duplicate:
            receipts.append({"leg_id": "0"})
        else:
            receipts.append({"leg_id": str(i)})
    return {"task_id": "T7.2", "authoritative": True, "concurrency": 10, "mode": mode, "leg_receipts": receipts}


def test_live_run_accepts_one_authoritative_100_leg_record() -> None:
    manifest = _manifest()
    manifest["live_runs"] = [_authoritative_run()]
    validator.validate_manifest(manifest, ROOT / "manifest.json")


def test_live_run_rejects_99_or_101_duplicate_or_keyless_receipts() -> None:
    for count in (99, 101):
        _error({**_manifest(), "live_runs": [_authoritative_run(count)]}, "LIVE_RUN_SINGLETON")
    _error({**_manifest(), "live_runs": [_authoritative_run(duplicate=True)]}, "LIVE_RUN_SINGLETON")
    _error({**_manifest(), "live_runs": [_authoritative_run(keyless=True)]}, "LIVE_RUN_SINGLETON")


def test_live_run_rejects_stale_5x2_ten_leg_contract() -> None:
    detail = _error({**_manifest(), "live_runs": [_authoritative_run(10, "5x2")]}, "LIVE_RUN_SINGLETON")
    assert "50x2" in detail


def test_live_run_rejects_two_authoritative_invocations() -> None:
    run = _authoritative_run()
    _error({**_manifest(), "live_runs": [run, copy.deepcopy(run)]}, "LIVE_RUN_SINGLETON")


def test_card_order_places_t04_after_t02_before_g0() -> None:
    order = validator.CARD_ORDER
    assert order.index("T0.2") < order.index("T0.4") < order.index("G0")
    g0 = validator.GATE_CARDS["G0"]
    assert g0[-2:] == ["T0.2", "T0.4"]
    assert g0 == ["T0.0", "T0.1", "T0.3", "T0.2", "T0.4"]
    relative = [card for card in order if card != "T0.4"]
    assert relative == [
        "T0.0", "T0.1", "T0.3", "T0.2", "G0",
        "T1.1", "T1.2", "G1", "T2.1", "T2.2", "T2.3", "G2",
        "T3.1", "T3.2", "G3", "T4.1", "T4.2", "T4.3", "G4",
        "T5.1", "T5.2", "T5.3", "T5.4", "T5.5", "G5",
        "T6.1", "T6.2", "T6.3", "G6", "T7.1", "T7.2", "T7.3", "G7",
    ]


def test_dependency_order_accepts_t04_and_rejects_unknown_cards() -> None:
    manifest = _manifest()
    manifest["tasks"] = [
        *manifest["tasks"],
        {"task_id": "T0.2", "label": "T0.2 [XHARD-REVIEW] contract", "model_route": "grok-4.6"},
        {"task_id": "T0.4", "label": "T0.4 [XHARD] plan amendment 50", "model_route": "grok-4.6"},
    ]
    validator.validate_manifest(manifest, ROOT / "manifest.json")
    unknown = _manifest()
    unknown["tasks"].append({"task_id": "T9.9", "label": "T9.9 [HARD] unknown", "model_route": "codex:gpt-5.6-luna"})
    _error(unknown, "DEPENDENCY_ORDER")


def test_broad_suite_is_a_singleton() -> None:
    manifest = _manifest()
    manifest["shards"] = [{"shard_id": "broad_suite_once_v1"}, {"shard_id": "broad_suite_once_v1"}]
    _error(manifest, "TEST_SINGLETON")


def test_complete_g6_requires_broad_suite_record() -> None:
    manifest = _manifest()
    manifest["gates"] = [{"gate_id": "G6", "status": "complete"}]
    _error(manifest, "DEPENDENCY_ORDER")


def test_process_completion_is_not_a_product_verdict() -> None:
    manifest = _manifest()
    manifest["live_runs"] = [{"authoritative": False, "legs": [{"assessment": {"verdict": "process_completed"}}]}]
    _error(manifest, "PROCESS_COMPLETION_VERDICT")
