from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    build_candidate_transaction,
    content_hash,
    validate_candidate_transaction,
)


def _transaction(*, layout_verification=None):
    envelope = {"schema_version": "2.0.0", "ops": []}
    return build_candidate_transaction(
        session_id="session",
        turn_id="0001",
        plan_hash="plan",
        delta_ops_envelope=envelope,
        delta_hash=content_hash(envelope),
        submit_graph_hash="submit",
        submit_structural_graph_hash="submit-structural",
        candidate_graph_hash="candidate",
        candidate_structural_graph_hash="candidate-structural",
        candidate_layout_graph_hash="a" * 64 if layout_verification else None,
        authority_receipt_hash="receipt",
        schema_witness={},
        replay_ok=True,
        candidate_matches=True,
        applyable=True,
        verification_kind="layout_structural_noop",
        layout_verification=layout_verification,
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


def test_legacy_layout_transaction_without_versioned_contract_remains_readable():
    transaction = _transaction()
    assert validate_candidate_transaction(transaction) == (True, None)
