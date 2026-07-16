from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.projection_registry_v1 import (
    CANDIDATE_TRANSACTION_V2,
    CANDIDATE_AUTHORITY_V1,
    PREPARED_AUTHORITY_V1,
    ContractError,
    canonical_json,
    classify_legacy_migration_v1,
    node_identity_v1,
    project_graph_v1,
    projection_reference_v1,
    validate_candidate_transaction_v2,
    validate_journal_durable_v1,
    validate_prepared_authority_v1,
)
from vibecomfy.comfy_nodes.agent.python_edit_v1 import apply_delta_v1_python
from vibecomfy.porting.edit.ops import EditOpParseError, normalize_delta_v1

CORPUS = json.loads((Path(__file__).parent / "fixtures/agent_edit/m1_projection_golden_v1.json").read_text())
UUID = "123e4567-e89b-12d3-a456-426614174000"


def test_shared_m1_golden_projection_corpus() -> None:
    for case in CORPUS["projection_cases"]:
        if "error" in case:
            with pytest.raises(ContractError) as caught:
                project_graph_v1(case["graph"], case["projection"])
            assert caught.value.code == case["error"]
            continue
        projected = project_graph_v1(case["graph"], case["projection"])
        assert projected == case["expected"]
        if "canonical" in case:
            assert canonical_json(projected) == case["canonical"]
        assert projection_reference_v1(case["graph"], case["projection"])["digest"] == case["digest"]


def _ref(projection: str) -> dict[str, str]:
    return {"kind": "projection_ref_v1", "projection": projection, "digest": "a" * 64}


def _authority(*, family: str = "structural") -> dict[str, object]:
    projection = "layout_v1" if family == "layout" else "structural_v1"
    value: dict[str, object] = {
        "contract_version": PREPARED_AUTHORITY_V1,
        "transaction_id": "tx-1", "candidate_id": "candidate-1", "workflow_id": UUID,
        "scope": {"kind": "root", "path": ""}, "session_id": "session-1", "turn_id": "turn-1",
        "operation": {"delta_contract": "delta_v1", "wire_version": "2.0.0", "ops": CORPUS["delta_ops"]},
        "operation_family": family, "precondition": _ref(projection), "postcondition": _ref(projection),
        "rollback_projection": projection, "restoration_strategy": {"contract_version": "inverse_delta_v1", "digest": "b" * 64, "payload": []},
        "plan_hash": "plan-1", "generation": 1, "lease_nonce": "nonce-1",
        "authority_receipt_contract_version": "authority_receipt_v2",
        "authority_receipt_delta_schema": "2.0.0",
        "authority_receipt_digest": "d" * 64,
    }
    if family == "layout": value["structural_witness"] = {**_ref("structural_v1"), "precondition_digest": "c" * 64, "postcondition_digest": "c" * 64}
    return value


def test_delta_v1_and_prepared_authority_are_strict_and_immutable() -> None:
    assert len(normalize_delta_v1({"delta_contract": "delta_v1", "wire_version": "2.0.0", "ops": CORPUS["delta_ops"]}).ops) == 6
    frozen = validate_prepared_authority_v1(_authority(), freeze=True)
    with pytest.raises(TypeError): frozen["generation"] = 2  # type: ignore[index]
    prepared = _authority()
    candidate = {key: value for key, value in prepared.items() if key not in {"generation", "lease_nonce"}}
    candidate["contract_version"] = CANDIDATE_AUTHORITY_V1
    assert validate_candidate_transaction_v2({
        "contract_version": CANDIDATE_TRANSACTION_V2,
        "state": "prepared",
        "candidate_authority": candidate,
        "prepared_authority": prepared,
    })
    with pytest.raises(ContractError) as caught:
        validate_candidate_transaction_v2({"contract_version": CANDIDATE_TRANSACTION_V2, "prepared_authority": prepared})
    assert caught.value.code == "missing_candidate_authority"
    for bad in ({"delta_contract": "delta_v1", "ops": []}, {"delta_contract": "delta_v1", "wire_version": "9.0.0", "ops": []}):
        with pytest.raises(EditOpParseError): normalize_delta_v1(bad)
    # This corpus is shared with browser tests: exact tuple arity is a wire
    # contract, so neither runtime may accept a partial or overlong target.
    for malformed in CORPUS["malformed_delta_ops"]:
        with pytest.raises(EditOpParseError):
            normalize_delta_v1({"delta_contract": "delta_v1", "wire_version": "2.0.0", "ops": [malformed["op"]]})
    invalid = _authority(); invalid["rollback_projection"] = "layout_v1"
    with pytest.raises(ContractError, match="Rollback"): validate_prepared_authority_v1(invalid)
    invalid = _authority(); invalid["scope"] = {"kind": "nested", "path": "definitions/x"}
    with pytest.raises(ContractError) as caught: validate_prepared_authority_v1(invalid)
    assert caught.value.code == "unsupported_scope"
    invalid = _authority(); invalid["contract_version"] = "prepared_authority_v9"
    with pytest.raises(ContractError) as caught: validate_prepared_authority_v1(invalid)
    assert caught.value.code == "unknown_authority_version"
    invalid = _authority(); invalid.pop("authority_receipt_contract_version")
    with pytest.raises(ContractError) as caught: validate_prepared_authority_v1(invalid)
    assert caught.value.code == "unknown_authority_receipt_version"
    invalid = _authority(); invalid["authority_receipt_digest"] = "ABC"
    with pytest.raises(ContractError) as caught: validate_prepared_authority_v1(invalid)
    assert caught.value.code == "invalid_authority_receipt_digest"


def test_m1_static_authority_guardrails() -> None:
    root = Path(__file__).parents[1]
    source = (root / "vibecomfy/comfy_nodes/agent/projection_registry_v1.py").read_text()
    session_source = (root / "vibecomfy/comfy_nodes/agent/session.py").read_text()
    identity_source = inspect.getsource(node_identity_v1)
    assert 'get("id")' not in identity_source
    from vibecomfy.comfy_nodes.agent.projection_registry_v1 import group_identity_v1
    assert 'get("title")' not in inspect.getsource(group_identity_v1)
    assert "workflow_v1 is forbidden" in source
    assert "legacy_bridge is not None" in source
    candidate_source = (root / "vibecomfy/comfy_nodes/agent/candidate_transaction.py").read_text()
    assert "uuid.uuid5" not in candidate_source
    assert "return _registry_canonical_json_bytes(value, ensure_ascii=False)" in candidate_source
    assert 'agent_edit_protocol = "v2_delta"' not in session_source
    assert "_load_turn_delta_ops(session_dir=session_dir, turn_id=turn_id) is not None" not in session_source
    assert "Legacy nonterminal authority is nonresumable" in session_source
    for duplicate_owner_symbol in (
        "def _natural_id_key",
        "def _normalize_structural_widget_value",
        "def _normalize_node_structural_widget_values",
        "def _layout_vector",
    ):
        assert duplicate_owner_symbol not in session_source
    assert "return _registry_structural_graph_projection(graph)" in session_source
    assert "return _registry_layout_graph_projection(graph)" in session_source

    agent_root = root / "vibecomfy/comfy_nodes/agent"
    web_root = root / "vibecomfy/comfy_nodes/web"
    allowed_projection_literal_owners = {
        agent_root / "projection_registry_v1.py",
        agent_root / "candidate_transaction.py",
        agent_root / "python_edit_v1.py",
        web_root / "projection_registry_v1.js",
        web_root / "prepared_authority_v1.js",
        web_root / "vibecomfy_roundtrip.js",
    }
    production_root = root / "vibecomfy"
    production_sources = [
        path for path in production_root.rglob("*")
        if path.suffix in {".py", ".js"} and "web_dist" not in path.parts
    ]
    for path in production_sources:
        text = path.read_text()
        if any(f'"{name}"' in text for name in ("structural_v1", "layout_v1", "workflow_v1")):
            assert path in allowed_projection_literal_owners, f"projection literal escaped its owner/adapter: {path}"

    duplicate_implementations = {
        "def _natural_id_key",
        "def _normalize_structural_widget_value",
        "def _normalize_node_structural_widget_values",
        "def _layout_vector",
    }
    for path in agent_root.glob("*.py"):
        if path == agent_root / "projection_registry_v1.py":
            continue
        text = path.read_text()
        assert not duplicate_implementations.intersection(
            marker for marker in duplicate_implementations if marker in text
        ), f"duplicate projection semantics outside registry: {path}"


def test_projection_reference_canonical_evidence_is_digest_bound() -> None:
    graph = CORPUS["projection_cases"][0]["graph"]
    reference = projection_reference_v1(graph, "structural_v1")
    from vibecomfy.comfy_nodes.agent.projection_registry_v1 import assert_projection_reference_v1
    assert assert_projection_reference_v1(reference, "structural_v1")
    reference["canonical"]["projection"] = "layout_v1"
    with pytest.raises(ContractError) as caught:
        assert_projection_reference_v1(reference, "structural_v1")
    assert caught.value.code == "projection_canonical_mismatch"
    reference = projection_reference_v1(graph, "structural_v1")
    reference["canonical"]["nodes"][0]["mode"] = 999
    with pytest.raises(ContractError) as caught:
        assert_projection_reference_v1(reference, "structural_v1")
    assert caught.value.code == "projection_digest_mismatch"


def test_layout_undo_and_legacy_policies_fail_closed() -> None:
    assert validate_prepared_authority_v1(_authority(family="layout"))
    broken = _authority(family="layout"); broken["structural_witness"]["postcondition_digest"] = "d" * 64  # type: ignore[index]
    with pytest.raises(ContractError) as caught: validate_prepared_authority_v1(broken)
    assert caught.value.code == "layout_structural_witness_mismatch"
    assert classify_legacy_migration_v1({"contract_version": "candidate_transaction_v1", "state": "finalized"})["classification"] == "legacy_terminal_read_only"
    assert classify_legacy_migration_v1({"contract_version": "candidate_transaction_v1", "state": "prepared"})["classification"] == "legacy_prepared_nonresumable"
    assert classify_legacy_migration_v1({})["classification"] == "legacy_non_resumable"
    assert validate_journal_durable_v1({
        "contract_version": "journal_durable_v1",
        "state": "finalized",
        "workflow_id": UUID,
        "baseline": {"structural_hash_before": "a" * 64, "structural_hash_after": "b" * 64},
        "identity_fence": {"transaction_id": "tx", "candidate_id": "candidate", "plan_hash": "plan", "generation": 1, "lease_nonce": "nonce"},
        "inverse_or_restore": {"contract_version": "inverse_delta_v1", "digest": "c" * 64, "payload": []},
    })


def test_python_only_delta_v1_end_to_end_uses_explicit_workflow_identity() -> None:
    """The supported Python path applies canonical UI JSON without browser globals."""
    graph = {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "mode": 0,
                "pos": [10, 20],
                "size": [320, 240],
                "properties": {"vibecomfy_uid": "sampler-1"},
                "widgets_values": [],
                "inputs": [],
                "outputs": [],
            }
        ],
        "links": [],
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }
    delta = {
        "delta_contract": "delta_v1",
        "wire_version": "2.0.0",
        "ops": [{"op": "set_mode", "target": ["", "sampler-1"], "mode": 4}],
    }

    result = apply_delta_v1_python(workflow_id=UUID, graph=graph, delta=delta)

    assert result["contract_version"] == "python_edit_result_v1"
    assert result["workflow_id"] == UUID
    assert result["scope"] == {"kind": "root", "path": ""}
    assert result["operation"] == delta
    assert result["graph"]["nodes"][0]["mode"] == 4
    assert result["precondition"]["projection"] == "structural_v1"
    assert result["postcondition"]["projection"] == "structural_v1"
    assert result["precondition"]["digest"] != result["postcondition"]["digest"]
    assert json.loads(json.dumps(result)) == result

    with pytest.raises(ContractError, match="workflow_id"):
        apply_delta_v1_python(workflow_id="not-a-workflow-uuid", graph=graph, delta=delta)
