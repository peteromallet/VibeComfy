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


def test_live_run_requires_one_authoritative_ten_leg_record() -> None:
    manifest = _manifest()
    manifest["live_runs"] = [{"task_id": "T7.2", "authoritative": True, "concurrency": 10, "mode": "5x2", "leg_receipts": [{"leg_id": str(i)} for i in range(9)]}]
    _error(manifest, "LIVE_RUN_SINGLETON")


def test_live_run_rejects_two_authoritative_invocations() -> None:
    manifest = _manifest()
    run = {"task_id": "T7.2", "authoritative": True, "concurrency": 10, "mode": "5x2", "leg_receipts": [{"leg_id": str(i)} for i in range(10)]}
    manifest["live_runs"] = [run, copy.deepcopy(run)]
    _error(manifest, "LIVE_RUN_SINGLETON")


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
