from __future__ import annotations

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    AuthorityReceipt,
    ReplayReceipt,
    ResponseMetadataHashes,
    stamp_response_with_authority,
)


def _receipt_error(error: str) -> AuthorityReceipt:
    return AuthorityReceipt(
        schema_version="2.0.0",
        session_id="sess",
        turn_id="turn",
        submit_graph_hash="a" * 64,
        submit_graph_bytes_sha256="b" * 64,
        accepted_batch_digest="c" * 64,
        cumulative_delta_hash="c" * 64,
        candidate_hash="d" * 64,
        schema_witness=None,
        schema_witness_hash=None,
        replay=ReplayReceipt(
            replay_ok=False,
            candidate_matches=False,
            recomputed_candidate_hash=None,
            persisted_candidate_hash="d" * 64,
            error=error,
            op_count=1,
            verification_kind="delta_replay",
        ),
        response_metadata=ResponseMetadataHashes(None, None, None),
        created_at="2026-08-29T00:00:00Z",
    )


def _landed_response(gate_a=True, gate_b=True, error_variant: str = "candidate_hash_mismatch") -> dict:
    return {
        "ok": True,
        "apply_eligible": True,
        "apply_eligible_reason": "applyable",
        "outcome": {"kind": "candidate"},
        "candidate": {"graph": {"nodes": [{"id": "21", "type": "SaveGLB"}], "links": []}, "state": "candidate"},
        "graph": {"nodes": [{"id": "21", "type": "SaveGLB"}], "links": []},
        "accepted_batch": [{"op": "set_node_field", "target": ["", "21", "filename_prefix"], "value": "3d/moge-top-down"}],
        "change_details": {
            "landed_operation_count": 1,
            "gate_a": gate_a,
            "gate_b": gate_b,
            "operations": [{"field": "filename_prefix"}],
            "batch_turns": [{"landed_op_count": 1, "batch_ok": True}],
        },
        "graph_unchanged": False,
        "message": "Edit landed.",
    }


def test_s1_landed_gate_pass_persists_candidate_instead_of_authority_rejected():
    receipt = _receipt_error("candidate_hash_mismatch")
    response = _landed_response(gate_a=True, gate_b=True)
    stamped = stamp_response_with_authority(response, receipt)
    assert "authority_receipt" in stamped
    assert stamped["authority_receipt"]["replay_error"] == "candidate_hash_mismatch"
    assert "candidate" in stamped and stamped["candidate"] is not None
    assert "graph" in stamped and stamped["graph"] is not None
    assert "accepted_batch" in stamped and len(stamped["accepted_batch"]) == 1
    assert stamped.get("graph_unchanged") is not True
    assert stamped.get("no_candidate_reason") != "authority_replay_mismatch"
    assert stamped.get("terminal_state") != "authority_rejected"
    assert "rejected_candidate" not in (stamped.get("audit") or {})


def test_s1_candidate_hash_mismatch_with_batch_turns_landed_preserved():
    receipt = _receipt_error("candidate_hash_mismatch")
    response = {
        "ok": True,
        "outcome": {"kind": "candidate"},
        "candidate": {"graph": {"nodes": [{"id": "34"}]}},
        "accepted_batch": [{"op": "set_node_field"}],
        "change_details": {
            "landed_operation_count": 0,
            "gate_a": True,
            "gate_b": True,
            "batch_turns": [{"landed_op_count": 1}, {"landed_op_count": 0}],
        },
        "graph_unchanged": False,
    }
    stamped = stamp_response_with_authority(response, receipt)
    assert "candidate" in stamped
    assert stamped.get("graph_unchanged") is not True


def test_s1_schema_gap_still_fail_closed_even_with_gate_pass():
    receipt = _receipt_error("missing_touched_schema: LayerMaskNode")
    response = _landed_response(gate_a=True, gate_b=True)
    stamped = stamp_response_with_authority(response, receipt)
    assert stamped.get("terminal_state") == "authority_rejected"
    assert stamped.get("graph_unchanged") is True
    assert "candidate" not in stamped or stamped.get("candidate") in (None, {})
    assert stamped.get("no_candidate_reason") == "authority_replay_mismatch"


def test_s1_phantom_landing_still_fail_closed():
    receipt = _receipt_error("phantom_landing_no_byte_change")
    response = _landed_response(gate_a=True, gate_b=True)
    stamped = stamp_response_with_authority(response, receipt)
    assert stamped.get("terminal_state") == "authority_rejected"
    assert stamped.get("graph_unchanged") is True


def test_s1_gate_false_not_preserved():
    receipt = _receipt_error("candidate_hash_mismatch")
    response = _landed_response(gate_a=False, gate_b=False)
    stamped = stamp_response_with_authority(response, receipt)
    assert stamped.get("terminal_state") == "authority_rejected"
    assert stamped.get("graph_unchanged") is True


def test_s1_fallback_accepted_batch_plus_candidate_without_explicit_gates():
    receipt = _receipt_error("candidate_hash_mismatch")
    response = {
        "ok": True,
        "outcome": {"kind": "candidate"},
        "candidate": {"graph": {"nodes": [{"id": 1}]}},
        "accepted_batch": [{"op": "set_node_field", "target": ["", "1", "value"]}],
        "graph_unchanged": False,
    }
    stamped = stamp_response_with_authority(response, receipt)
    assert "candidate" in stamped
    assert stamped.get("graph_unchanged") is not True


def test_s1_debug_gates_fallback_for_threaded_r9():
    receipt = _receipt_error("candidate_hash_mismatch")
    response = {
        "ok": True,
        "outcome": {"kind": "candidate"},
        "candidate": {"graph": {"nodes": [{"id": 1}]}},
        "accepted_batch": [{"op": "set_node_field"}],
        "change_details": {"landed_operation_count": 1},
        "debug": {"gates": {"edit_scope_ok": True, "isomorphic_ok": True}},
        "graph_unchanged": False,
    }
    stamped = stamp_response_with_authority(response, receipt)
    assert "candidate" in stamped
