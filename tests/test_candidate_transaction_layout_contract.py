import pytest

from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    build_candidate_transaction,
    content_hash,
    validate_candidate_transaction,
)


def _transaction(*, layout_verification=None, state="candidate_ready"):
    envelope = {"schema_version": "2.0.0", "ops": []}
    submit_graph = {
        "nodes": [
            {
                "vibecomfy_uid": "node-1",
                "type": "PreviewImage",
                "pos": [0, 0],
                "size": [200, 100],
            }
        ],
        "links": [],
        "groups": [],
    }
    candidate_graph = {
        **submit_graph,
        "nodes": [{**submit_graph["nodes"][0], "pos": [300, 100]}],
    }
    return build_candidate_transaction(
        workflow_id="123e4567-e89b-12d3-a456-426614174000",
        session_id="session",
        turn_id="0001",
        plan_hash="plan",
        submit_graph=submit_graph,
        candidate_graph=candidate_graph,
        delta_ops_envelope=envelope,
        delta_hash=content_hash(envelope),
        submit_graph_hash="submit",
        submit_structural_graph_hash="submit-structural",
        candidate_graph_hash="candidate",
        candidate_structural_graph_hash="candidate-structural",
        candidate_layout_graph_hash="a" * 64 if layout_verification else None,
        authority_receipt_hash="f" * 64,
        schema_witness={},
        replay_ok=True,
        candidate_matches=True,
        applyable=True,
        verification_kind="layout_structural_noop",
        layout_verification=layout_verification,
        state=state,
    )


def test_versioned_layout_verification_contract_is_valid():
    transaction = _transaction(
        layout_verification={
            "contract_version": "layout_verification_v1",
            "projection": "browser_layout_v1",
            "candidate_layout_graph_hash": "a" * 64,
        }
    )
    assert validate_candidate_transaction(transaction) == (True, None)


def test_unknown_layout_verification_contract_fails_closed():
    transaction = _transaction(
        layout_verification={
            "contract_version": "layout_verification_v999",
            "projection": "browser_layout_v1",
            "candidate_layout_graph_hash": "a" * 64,
        }
    )
    assert validate_candidate_transaction(transaction) == (
        False,
        "unsupported_layout_verification_contract",
    )


def test_typed_layout_authority_does_not_require_m0_browser_layout_metadata():
    transaction = _transaction()
    assert validate_candidate_transaction(transaction) == (True, None)


def test_new_v2_issuance_rejects_legacy_state_aliases():
    with pytest.raises(ValueError, match="Unknown candidate transaction state"):
        _transaction(state="candidate")


def test_new_candidate_authority_requires_explicit_workflow_uuid_and_receipt_digest():
    with pytest.raises(ValueError, match="workflow_id"):
        transaction = _transaction()
        build_candidate_transaction(
            workflow_id="session-derived-id",
            session_id=transaction["session_id"],
            turn_id=transaction["turn_id"],
            plan_hash=transaction["plan_hash"],
            submit_graph=transaction["candidate_authority"]["precondition"]["canonical"],
            candidate_graph=transaction["candidate_authority"]["postcondition"]["canonical"],
            delta_ops_envelope=transaction["plan"]["delta_ops_envelope"],
            delta_hash=transaction["plan"]["delta_hash"],
            submit_graph_hash="submit",
            submit_structural_graph_hash="before",
            candidate_graph_hash="candidate",
            candidate_structural_graph_hash="after",
            authority_receipt_hash="f" * 64,
            schema_witness={},
            replay_ok=True,
            candidate_matches=True,
            applyable=True,
        )

    with pytest.raises(ValueError, match="64-hex"):
        build_candidate_transaction(
            workflow_id="123e4567-e89b-12d3-a456-426614174000",
            session_id="session",
            turn_id="0001",
            plan_hash="plan",
            submit_graph={"nodes": [], "links": [], "groups": []},
            candidate_graph={"nodes": [], "links": [], "groups": []},
            delta_ops_envelope={"schema_version": "2.0.0", "ops": []},
            delta_hash=content_hash({"schema_version": "2.0.0", "ops": []}),
            submit_graph_hash="submit",
            submit_structural_graph_hash="before",
            candidate_graph_hash="candidate",
            candidate_structural_graph_hash="after",
            authority_receipt_hash="ABC",
            schema_witness={},
            replay_ok=True,
            candidate_matches=True,
            applyable=True,
        )
