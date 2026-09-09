import pytest

from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    build_schema_witness,
    build_candidate_transaction,
    content_hash,
    validate_candidate_transaction,
)
from vibecomfy.comfy_nodes.agent.layout_operation_v1 import (
    LayoutOperationError,
    assert_layout_operation_envelope,
    compute_layout_operation_digest,
)
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.schema.types import (
    FrozenSchemaSnapshotProvider,
    SchemaSnapshotError,
    capture_schema_snapshot,
    schema_payload_from_node_schema,
)


REVISION_ID = "a" * 64
PARENT_REVISION = ""
WORKFLOW_ID = "123e4567-e89b-12d3-a456-426614174000"
_DEFAULT_SCHEMA_WITNESS = object()


def _bundle_metadata():
    return {
        "revision_id": REVISION_ID,
        "parent_revision": PARENT_REVISION,
        "workflow_identity": WORKFLOW_ID,
        "python_path": "/tmp/candidate.py",
        "semantic_digest": "b" * 64,
        "sidecar_state": "absent",
        "ui_digest": "",
    }


def _layout_schema_snapshot():
    schema = NodeSchema(
        class_type="PreviewImage",
        pack="core",
        inputs={"images": InputSpec("IMAGE", required=True)},
        outputs=[],
    )
    return capture_schema_snapshot(
        class_types=["PreviewImage"],
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": {
                "PreviewImage": schema_payload_from_node_schema(
                    "PreviewImage", schema
                )
            },
            "missing_classes": [],
        },
        node_classes={"node-1": "PreviewImage"},
    )


def _layout_operation_envelope():
    ops = [{"op": "set_node_geometry", "uid": "node-1", "pos": [300, 100]}]
    digest = compute_layout_operation_digest(
        ops, snapshot=_layout_schema_snapshot()
    )
    return {
        "contract_version": "layout_operation_v1",
        "wire_version": "1.0.0",
        "ops": ops,
        "digest": digest,
    }


def _transaction(
    *,
    layout_verification=None,
    state="candidate_ready",
    schema_witness=_DEFAULT_SCHEMA_WITNESS,
):
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
    if schema_witness is _DEFAULT_SCHEMA_WITNESS:
        schema_witness = build_schema_witness(
            schema_provider=FrozenSchemaSnapshotProvider(_layout_schema_snapshot()),
            submit_graph=submit_graph,
            candidate_payload=candidate_graph,
            delta_envelope={"schema_version": "2.0.0", "ops": []},
        )
    return build_candidate_transaction(
        workflow_id=WORKFLOW_ID,
        session_id="session",
        turn_id="0001",
        plan_hash="plan",
        revision_id=REVISION_ID,
        parent_revision=PARENT_REVISION,
        submit_graph=submit_graph,
        candidate_graph=candidate_graph,
        accepted_batch=[],
        delta_hash=content_hash({"schema_version": "2.0.0", "ops": []}),
        submit_graph_hash="submit",
        submit_structural_graph_hash="submit-structural",
        candidate_graph_hash="candidate",
        candidate_structural_graph_hash="candidate-structural",
        candidate_layout_graph_hash="a" * 64 if layout_verification else None,
        authority_receipt_hash="a" * 64,
        schema_witness=schema_witness,
        replay_ok=True,
        candidate_matches=True,
        applyable=True,
        verification_kind="layout_structural_noop",
        layout_verification=layout_verification,
        layout_operation_envelope=_layout_operation_envelope(),
        state=state,
        bundle_digests=_bundle_metadata(),
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


def test_snapshotless_layout_helpers_cannot_bypass_candidate_issuance_schema_custody():
    """Pure digest verification works, but authority issuance still requires a snapshot."""
    envelope = _layout_operation_envelope()
    assert assert_layout_operation_envelope(envelope) == envelope

    with pytest.raises(SchemaSnapshotError) as caught:
        _transaction(schema_witness={})
    assert caught.value.code == "missing_schema_snapshot"


def test_candidate_issuance_rejects_snapshot_missing_the_touched_node_class():
    missing_snapshot = capture_schema_snapshot(
        class_types=["PreviewImage"],
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": {},
            "missing_classes": ["PreviewImage"],
        },
        node_classes={"node-1": "PreviewImage"},
    )
    witness = build_schema_witness(
        schema_provider=FrozenSchemaSnapshotProvider(missing_snapshot),
        submit_graph=None,
        candidate_payload=None,
        delta_envelope=None,
    )

    with pytest.raises(LayoutOperationError) as caught:
        _transaction(schema_witness=witness)
    assert caught.value.code == "missing_touched_schema"


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
            revision_id=REVISION_ID,
            parent_revision=PARENT_REVISION,
            submit_graph=transaction["candidate_authority"]["precondition"]["canonical"],
            candidate_graph=transaction["candidate_authority"]["postcondition"]["canonical"],
            accepted_batch=transaction["plan"]["accepted_batch"],
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
            bundle_digests=_bundle_metadata(),
        )

    with pytest.raises(ValueError, match="64-hex"):
        build_candidate_transaction(
            workflow_id=WORKFLOW_ID,
            session_id="session",
            turn_id="0001",
            plan_hash="plan",
            revision_id=REVISION_ID,
            parent_revision=PARENT_REVISION,
            submit_graph={"nodes": [], "links": [], "groups": []},
            candidate_graph={"nodes": [], "links": [], "groups": []},
            accepted_batch=[],
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
            bundle_digests=_bundle_metadata(),
        )
