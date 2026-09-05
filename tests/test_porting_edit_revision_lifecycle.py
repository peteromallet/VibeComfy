from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.projection_registry_v1 import (
    ContractError,
    revision_identity_v1,
    validate_journal_durable_v1,
)
from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    build_candidate_transaction,
    validate_candidate_transaction,
)
from vibecomfy.testing.canonical import canonical_digest
from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import WorkflowBundleError, _make_bundle


REVISION = "a" * 64
PARENT = "b" * 64


def _graph() -> dict:
    # Keep the fixture depth-2-shaped: the lifecycle identity is independent
    # of the root-only graph CAS and must survive recursive captures.
    return {
        "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
        "nodes": [
            {
                "id": 1,
                "type": "Integer",
                "mode": 0,
                "pos": [0, 0],
                "size": [100, 80],
                "properties": {"vibecomfy_uid": "root"},
                "widgets_values": [1],
                "inputs": [],
                "outputs": [],
            }
        ],
        "links": [],
        "groups": [],
        "definitions": [
            {
                "name": "outer",
                "nodes": [],
                "definitions": [{"name": "inner", "nodes": []}],
            }
        ],
    }


def _minimal_transaction() -> dict:
    graph = _graph()
    delta = [{"op": "set_mode", "target": ["", "root"], "mode": 4}]
    witness = {
        "contract_version": "schema_snapshot_v1",
        "provider_mode": "test",
        "witness_hash": "c" * 64,
        "schemas": {},
        "missing_class_types": [],
    }
    return build_candidate_transaction(
        workflow_id="123e4567-e89b-12d3-a456-426614174000",
        session_id="session",
        turn_id="0001",
        plan_hash="d" * 64,
        revision_id=REVISION,
        parent_revision="",
        submit_graph=graph,
        candidate_graph=graph,
        accepted_batch=delta,
        submit_graph_hash="e" * 64,
        submit_structural_graph_hash="f" * 64,
        candidate_graph_hash="0" * 64,
        candidate_structural_graph_hash="1" * 64,
        authority_receipt_hash="2" * 64,
        schema_witness=witness,
        replay_ok=True,
        candidate_matches=True,
        applyable=True,
        bundle_digests={
            "revision_id": REVISION,
            "parent_revision": "",
            "workflow_identity": "123e4567-e89b-12d3-a456-426614174000",
            "python_path": "/tmp/candidate.py",
            "semantic_digest": "3" * 64,
            "sidecar_state": "absent",
            "ui_digest": "",
        },
    )


def test_revision_identity_is_closed_and_parent_is_not_inferred() -> None:
    assert revision_identity_v1(REVISION, PARENT) == (REVISION, PARENT)
    assert revision_identity_v1(REVISION, "") == (REVISION, "")
    with pytest.raises(ContractError, match="revision_id"):
        revision_identity_v1("", "")
    with pytest.raises(ContractError, match="parent_revision"):
        revision_identity_v1(REVISION, "not-a-digest")


def test_candidate_transaction_carries_exact_bundle_identity() -> None:
    transaction = _minimal_transaction()
    assert transaction["revision_id"] == REVISION
    assert transaction["parent_revision"] == ""
    assert transaction["candidate_authority"]["revision_id"] == REVISION
    assert transaction["bundle"]["revision_id"] == REVISION
    assert validate_candidate_transaction(transaction) == (True, None)

    mismatched = json.loads(json.dumps(transaction))
    mismatched["parent_revision"] = PARENT
    assert validate_candidate_transaction(mismatched)[0] is False


def test_journal_durable_revision_fence_requires_exact_pair() -> None:
    record = {
        "contract_version": "journal_durable_v1",
        "state": "finalized",
        "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
        "revision_id": REVISION,
        "parent_revision": PARENT,
        "baseline": {
            "structural_hash_before": "1" * 64,
            "structural_hash_after": "2" * 64,
        },
        "identity_fence": {
            "transaction_id": "tx",
            "candidate_id": "candidate",
            "plan_hash": "3" * 64,
            "generation": 1,
            "lease_nonce": "nonce",
            "revision_id": REVISION,
            "parent_revision": PARENT,
        },
        "inverse_or_restore": {
            "contract_version": "baseline_snapshot_v1",
            "ref": "original.ui.json",
            "digest": canonical_digest(
                {"contract_version": "baseline_snapshot_v1", "ref": "original.ui.json"}
            ),
        },
    }
    assert validate_journal_durable_v1(record)["revision_id"] == REVISION
    broken = json.loads(json.dumps(record))
    broken["identity_fence"]["revision_id"] = "4" * 64
    with pytest.raises(ContractError, match="revision fence"):
        validate_journal_durable_v1(broken)


def test_bundle_parent_requires_explicit_journal_evidence() -> None:
    workflow = VibeWorkflow("bundle", WorkflowSource("bundle"))
    with pytest.raises(WorkflowBundleError, match="unknown parent revision"):
        _make_bundle(
            workflow,
            python_path=Path("bundle.py"),
            ui_sidecar=None,
            provenance={"operation": "captured"},
            operation="captured",
            parent_revision=PARENT,
        )
    bundle = _make_bundle(
        workflow,
        python_path=Path("bundle.py"),
        ui_sidecar=None,
        provenance={"operation": "captured"},
        operation="captured",
        parent_revision=PARENT,
        parent_evidence={"revision_id": PARENT, "workflow_identity": workflow.id},
    )
    assert bundle.parent_revision == PARENT
    assert bundle.provenance["revision_evidence"]


def test_real_session_fixture_carries_pair_identity_through_prepare_finalize(tmp_path, monkeypatch) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import (
        _setup_v2_session_with_candidate,
        canonical_candidate_graph,
        finalize_turn_transaction,
        prepare_turn_transaction,
    )
    from vibecomfy.workflow_bundle import ApprovedProjectionRecord, WorkflowBundle

    compile_calls: list[str] = []
    compile_paths: list[Path | None] = []

    def compile_once(self):
        compile_calls.append(self.revision_id)
        compile_paths.append(self.python_path)
        # The staged source is real and reloadable, but this fixture's
        # SaveImage node is intentionally absent from the local Comfy schema.
        # Keep the compile boundary real (and count it exactly once) with a
        # deterministic approval seam rather than weakening finalize guards.
        api_projection = {"workflow_revision": self.revision_id}
        return ApprovedProjectionRecord(
            revision_id=self.revision_id,
            selected_variant=self.workflow.default_variant,
            input_binding={},
            api_projection=api_projection,
            ui_projection={},
            api_digest=canonical_digest(api_projection),
        )

    monkeypatch.setattr(WorkflowBundle, "compile", compile_once)

    root, session_id, turn_id, candidate_hash, structural_hash, plan_hash = (
        _setup_v2_session_with_candidate(tmp_path)
    )
    response = json.loads(
        (root / session_id / "turns" / turn_id / "response.json").read_text(encoding="utf-8")
    )
    transaction = response["candidate_transaction"]
    bundle = transaction["bundle"]
    final_python = Path(bundle["python_path"])
    assert final_python.parent.name == plan_hash
    assert final_python.is_file()
    assert not (final_python.parent / ".pending" / "candidate.py").exists()
    assert "approval" not in transaction

    prepared = prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={"plan_hash": plan_hash, "candidate_graph_hash": candidate_hash},
    )
    assert isinstance(prepared, dict)
    assert (prepared["revision_id"], prepared["parent_revision"]) == (
        transaction["revision_id"],
        transaction["parent_revision"],
    )
    graph = canonical_candidate_graph(root, session_id, turn_id)
    finalize_payload = {
        "plan_hash": plan_hash,
        "generation": prepared["generation"],
        "lease_nonce": prepared["lease_nonce"],
        "post_apply_hash": structural_hash,
        "post_apply_graph": graph,
        "applied_delta_hash": prepared["candidate_transaction"]["plan"]["delta_hash"],
        "post_apply_hash_verified": True,
        "browser_verified": True,
    }
    finalized = finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload=finalize_payload,
    )
    assert isinstance(finalized, dict), getattr(
        finalized, "agent_failure_context", repr(finalized)
    )
    assert finalized["revision_id"] == transaction["revision_id"]
    assert finalized["parent_revision"] == transaction["parent_revision"]
    assert compile_calls == [transaction["revision_id"]]
    assert compile_paths == [final_python]
    replayed = finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload=finalize_payload,
    )
    assert isinstance(replayed, dict), getattr(
        replayed, "agent_failure_context", repr(replayed)
    )
    assert replayed["idempotent_replay"] is True
    assert compile_calls == [transaction["revision_id"]]
    assert compile_paths == [final_python]


def test_real_session_rejects_identity_and_staged_metadata_damage_before_replay(tmp_path) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import _setup_v2_session_with_candidate
    from vibecomfy.comfy_nodes.agent import session as agent_session

    root, session_id, turn_id, candidate_hash, _structural_hash, plan_hash = (
        _setup_v2_session_with_candidate(tmp_path)
    )
    session_dir = root / session_id
    turn_dir = session_dir / "turns" / turn_id
    response_path = turn_dir / "response.json"
    response_before = response_path.read_bytes()
    state_before = agent_session.read_state(session_dir)
    lifecycle_path = turn_dir / "transactions" / plan_hash / "lifecycle_events.jsonl"
    lifecycle_before = lifecycle_path.read_bytes() if lifecycle_path.is_file() else None
    transaction = json.loads(response_before.decode("utf-8"))["candidate_transaction"]

    missing = agent_session.prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={"plan_hash": plan_hash, "candidate_graph_hash": candidate_hash},
    )
    assert not isinstance(missing, dict)
    assert "exact captured bundle revision" in missing.agent_failure_context["explanation"]

    conflicting = agent_session.prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": plan_hash,
            "candidate_graph_hash": candidate_hash,
            "revision_id": "0" * 64,
            "parent_revision": transaction["parent_revision"],
        },
    )
    assert not isinstance(conflicting, dict)
    assert "exact captured bundle revision" in conflicting.agent_failure_context["explanation"]

    for field, value in (
        ("python_path", "candidate.py"),
        ("semantic_digest", ""),
        ("sidecar_path", str(Path(transaction["bundle"]["python_path"]).with_name("other.vibe.json"))),
    ):
        damaged = json.loads(json.dumps(transaction))
        damaged["bundle"][field] = value
        with pytest.raises((ContractError, ValueError)):
            agent_session._reload_captured_bundle(transaction=damaged, compile_approval=False)

    assert response_path.read_bytes() == response_before
    assert agent_session.read_state(session_dir) == state_before
    assert (lifecycle_path.read_bytes() if lifecycle_path.is_file() else None) == lifecycle_before


def test_failed_pair_publication_restores_prior_pair_and_writes_no_final_event(
    tmp_path, monkeypatch
) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import (
        _setup_v2_session_with_candidate,
        canonical_candidate_graph,
    )
    from vibecomfy.comfy_nodes.agent import session as agent_session

    root, session_id, turn_id, _candidate_hash, _structural_hash, plan_hash = (
        _setup_v2_session_with_candidate(tmp_path)
    )
    turn_dir = root / session_id / "turns" / turn_id
    transaction = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))["candidate_transaction"]
    metadata, pending = agent_session._capture_candidate_bundle(
        graph=canonical_candidate_graph(root, session_id, turn_id),
        turn_dir=turn_dir,
        workflow_id=transaction["bundle"]["workflow_identity"],
        parent_revision=transaction["parent_revision"],
        session_dir=root / session_id,
        plan_hash=plan_hash,
    )
    final_python = Path(metadata["python_path"])
    final_sidecar = Path(metadata["sidecar_path"])
    previous_pair = (final_python.read_bytes(), final_sidecar.read_bytes())
    lifecycle = final_python.parent / "lifecycle_events.jsonl"
    lifecycle_before = lifecycle.read_bytes() if lifecycle.is_file() else None
    pending["python_path"].write_bytes(b"injected staged source")
    real_replace = agent_session.os.replace
    calls = 0

    def fail_after_python(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected sidecar publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(agent_session.os, "replace", fail_after_python)
    with pytest.raises(OSError, match="injected sidecar publication failure"):
        agent_session._publish_pending_bundle(metadata, pending)

    assert (final_python.read_bytes(), final_sidecar.read_bytes()) == previous_pair
    assert not pending["python_path"].exists()
    assert not pending["sidecar_path"].exists()
    assert (lifecycle.read_bytes() if lifecycle.is_file() else None) == lifecycle_before
    assert not (final_python.parent / "finalized.json").exists()
