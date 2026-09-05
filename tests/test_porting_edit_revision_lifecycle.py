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


def _stub_bundle_compile(monkeypatch):
    from vibecomfy.workflow_bundle import ApprovedProjectionRecord, WorkflowBundle

    compile_calls: list[str] = []
    compile_paths: list[Path | None] = []

    def compile_once(self):
        compile_calls.append(self.revision_id)
        compile_paths.append(self.python_path)
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
    return compile_calls, compile_paths


def _txn_dir(root: Path, session_id: str, turn_id: str, plan_hash: str) -> Path:
    return root / session_id / "turns" / turn_id / "transactions" / plan_hash


def _response_transaction(root: Path, session_id: str, turn_id: str) -> dict:
    return json.loads(
        (root / session_id / "turns" / turn_id / "response.json").read_text(encoding="utf-8")
    )["candidate_transaction"]


def _record_v2_turn(
    tmp_path: Path,
    *,
    root: Path | None = None,
    session_id: str = "s1",
    label: str = "v2-prep-test",
    parent_revision: str = "",
    seed_parent_revision: str | None = None,
    workflow_id: str | None = None,
    submit_graph: dict | None = None,
):
    from tests.test_comfy_nodes_agent_backend_spine import (
        _Provider,
        _frozen_ingest_provider,
        _request_graph,
        _schema_with_inputs,
        allocate_turn,
        payload_hash,
        record_idempotent_response,
        structural_graph_hash,
        v2_mutation_plan_hash,
    )
    from vibecomfy.comfy_nodes.agent.authority_receipts import recompute_apply
    from vibecomfy.comfy_nodes.agent.session import _resolve_stable_workflow_id
    from vibecomfy.schema import InputSpec
    from vibecomfy.workflow_bundle import capture_bundle

    sessions = root if root is not None else tmp_path / "sessions"
    request = _request_graph(label)
    if submit_graph is not None:
        request["graph"] = json.loads(json.dumps(submit_graph))
    if workflow_id is not None:
        request["workflow_id"] = workflow_id
    request["client_live_canvas_token"] = f"live:rev:1:client-{label}"
    allocation = allocate_turn(
        session_root=sessions,
        session_id=session_id,
        request_payload=request,
    )
    turn_id = str(allocation.context.turn_id)
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "1", "filename_prefix"],
                "value": f"{label}-cand",
            }
        ],
    }
    schema_provider = _Provider(
        {
            "SaveImage": _schema_with_inputs(
                "SaveImage",
                filename_prefix=InputSpec(type="STRING", required=True, default="ComfyUI"),
            )
        }
    )
    ok, candidate_graph, error, _ = recompute_apply(
        request["graph"],
        envelope,
        schema_provider=schema_provider,
    )
    assert ok and candidate_graph is not None, error
    candidate_graph_hash = payload_hash(candidate_graph)
    structural_hash = structural_graph_hash(candidate_graph)
    submit_structural_hash = structural_graph_hash(request["graph"])
    plan_hash = v2_mutation_plan_hash(
        delta_ops_envelope=envelope,
        structural_hash_before=submit_structural_hash,
        structural_hash_after=structural_hash,
    )
    resolved_workflow_id = _resolve_stable_workflow_id(
        request, request.get("scope_metadata"), session_id, request["graph"]
    )
    seed_parent = parent_revision if seed_parent_revision is None else seed_parent_revision
    seed_graph = dict(candidate_graph)
    seed_graph["workflow_id"] = resolved_workflow_id
    parent_evidence = None
    if seed_parent:
        parent_evidence = {
            "revision_id": seed_parent,
            "workflow_identity": resolved_workflow_id,
        }
    seed = capture_bundle(
        seed_graph,
        allocation.turn_dir / "seed.py",
        {"operation": "captured"},
        parent_revision=seed_parent,
        parent_evidence=parent_evidence,
    )
    (allocation.turn_dir / "seed.py").unlink(missing_ok=True)
    (allocation.turn_dir / "seed.vibe.json").unlink(missing_ok=True)
    request["revision_id"] = seed.revision_id
    request["parent_revision"] = parent_revision
    (allocation.turn_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")
    immediate_response = {
        "ok": True,
        "turn_id": turn_id,
        "graph": candidate_graph,
        "candidate": {
            "graph": candidate_graph,
            "plan_hash": plan_hash,
            "structural_hash_before": submit_structural_hash,
            "structural_hash_after": structural_hash,
        },
        "eligibility": {"applyable": True},
        "agent_edit_protocol": "v2_delta",
        "accepted_batch": [{"op": op} for op in envelope["ops"]],
    }
    record_idempotent_response(
        session_root=sessions,
        session_id=session_id,
        scope="edit",
        idempotency_key=None,
        request_hash=allocation.request_hash,
        response=immediate_response,
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
        schema_provider=_frozen_ingest_provider(schema_provider, request["graph"]),
    )
    return (
        sessions,
        session_id,
        turn_id,
        candidate_graph_hash,
        structural_hash,
        plan_hash,
        immediate_response,
    )


def test_real_session_fixture_carries_pair_identity_through_prepare_finalize(tmp_path, monkeypatch) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import (
        _setup_v2_session_with_candidate,
        canonical_candidate_graph,
        finalize_turn_transaction,
        prepare_turn_transaction,
    )

    compile_calls, compile_paths = _stub_bundle_compile(monkeypatch)
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

    wrong_revision = dict(finalize_payload)
    wrong_revision["revision_id"] = "0" * 64
    mismatched_revision = finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload=wrong_revision,
    )
    assert not isinstance(mismatched_revision, dict)
    assert mismatched_revision.ok is False

    wrong_generation = dict(finalize_payload)
    wrong_generation["generation"] = int(prepared["generation"]) + 1
    mismatched_generation = finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload=wrong_generation,
    )
    assert not isinstance(mismatched_generation, dict)
    assert mismatched_generation.ok is False
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


def test_real_session_journal_backed_child_and_rejected_parent(tmp_path) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import (
        _setup_v2_session_with_candidate,
        prepare_turn_transaction,
    )
    from vibecomfy.comfy_nodes.agent.candidate_transaction import CANDIDATE_TRANSACTION_FILENAME

    root, session_id, turn_id, candidate_hash, _structural_hash, plan_hash = (
        _setup_v2_session_with_candidate(tmp_path)
    )
    parent_transaction = _response_transaction(root, session_id, turn_id)
    prepared = prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={"plan_hash": plan_hash, "candidate_graph_hash": candidate_hash},
    )
    assert isinstance(prepared, dict)
    parent_revision = prepared["revision_id"]
    parent_python_path = Path(parent_transaction["bundle"]["python_path"])
    parent_python = parent_python_path.read_bytes()
    parent_sidecar_path = parent_python_path.with_suffix(".vibe.json")
    parent_sidecar = parent_sidecar_path.read_bytes()
    parent_receipt_path = root / session_id / "turns" / turn_id / "authority" / "receipt.json"
    parent_receipt = parent_receipt_path.read_bytes()
    parent_txn = _txn_dir(root, session_id, turn_id, plan_hash) / CANDIDATE_TRANSACTION_FILENAME
    parent_txn_bytes = parent_txn.read_bytes()

    child = _record_v2_turn(
        tmp_path,
        root=root,
        session_id=session_id,
        label="v2-child",
        parent_revision=parent_revision,
    )
    child_turn = child[2]
    child_plan = child[5]
    child_transaction = _response_transaction(root, session_id, child_turn)
    assert child_transaction["parent_revision"] == parent_revision
    assert child_transaction["revision_id"] != parent_revision
    assert child_transaction["bundle"]["parent_revision"] == parent_revision
    assert Path(child_transaction["bundle"]["python_path"]).is_file()
    assert not (_txn_dir(root, session_id, child_turn, child_plan) / ".pending").exists()

    with pytest.raises(ValueError, match="parent revision is not backed"):
        _record_v2_turn(
            tmp_path,
            root=root,
            session_id=session_id,
            label="v2-unknown-parent",
            parent_revision="c" * 64,
            seed_parent_revision="",
        )
    unknown_turns = sorted(
        path for path in (root / session_id / "turns").iterdir() if path.is_dir()
    )
    unknown_turn = unknown_turns[-1]
    assert not (unknown_turn / "response.json").exists()
    assert not (unknown_turn / "authority" / "receipt.json").exists()
    assert list(unknown_turn.rglob("candidate.py")) == []
    assert list(unknown_turn.rglob(CANDIDATE_TRANSACTION_FILENAME)) == []
    assert list(unknown_turn.rglob(".pending/candidate.py")) == []
    assert list(unknown_turn.rglob("finalized.json")) == []
    assert list(unknown_turn.rglob("lifecycle_events.jsonl")) == []
    assert list(unknown_turn.rglob("approval*.json")) == []
    assert parent_txn.read_bytes() == parent_txn_bytes
    assert parent_python_path.read_bytes() == parent_python
    assert parent_sidecar_path.read_bytes() == parent_sidecar
    assert parent_receipt_path.read_bytes() == parent_receipt

    with pytest.raises(ValueError, match="parent revision is not backed"):
        _record_v2_turn(
            tmp_path,
            root=root,
            session_id=session_id,
            label="v2-mismatched-parent",
            parent_revision=parent_revision,
            workflow_id="123e4567-e89b-12d3-a456-426614174999",
        )
    assert parent_txn.read_bytes() == parent_txn_bytes
    assert Path(parent_transaction["bundle"]["python_path"]).read_bytes() == parent_python
    assert parent_sidecar_path.read_bytes() == parent_sidecar
    assert parent_receipt_path.read_bytes() == parent_receipt


def test_real_session_recapture_invalidates_old_approval(tmp_path, monkeypatch) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import (
        _setup_v2_session_with_candidate,
        canonical_candidate_graph,
        finalize_turn_transaction,
        prepare_turn_transaction,
    )

    compile_calls, _compile_paths = _stub_bundle_compile(monkeypatch)
    root, session_id, turn_id, candidate_hash, structural_hash, plan_hash = (
        _setup_v2_session_with_candidate(tmp_path)
    )
    parent_transaction = _response_transaction(root, session_id, turn_id)
    prepared = prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={"plan_hash": plan_hash, "candidate_graph_hash": candidate_hash},
    )
    assert isinstance(prepared, dict)
    graph = canonical_candidate_graph(root, session_id, turn_id)
    finalized = finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": plan_hash,
            "generation": prepared["generation"],
            "lease_nonce": prepared["lease_nonce"],
            "post_apply_hash": structural_hash,
            "post_apply_graph": graph,
            "applied_delta_hash": prepared["candidate_transaction"]["plan"]["delta_hash"],
            "post_apply_hash_verified": True,
            "browser_verified": True,
        },
    )
    assert isinstance(finalized, dict), getattr(finalized, "agent_failure_context", repr(finalized))
    parent_revision = finalized["revision_id"]
    assert compile_calls == [parent_revision]
    assert finalized["receipt"]["receipt"]["approval"]["revision_id"] == parent_revision

    child = _record_v2_turn(
        tmp_path,
        root=root,
        session_id=session_id,
        label="v2-recapture",
        parent_revision=parent_revision,
        submit_graph=graph,
    )
    child_turn, child_hash, child_plan = child[2], child[3], child[5]
    child_transaction = _response_transaction(root, session_id, child_turn)
    assert child_transaction["revision_id"] != parent_revision
    assert child_transaction["parent_revision"] == parent_revision
    stale_parent = prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=child_turn,
        request_payload={
            "plan_hash": child_plan,
            "candidate_graph_hash": child_hash,
            "revision_id": parent_revision,
            "parent_revision": parent_transaction["parent_revision"],
        },
    )
    assert not isinstance(stale_parent, dict)
    assert "exact captured bundle revision" in stale_parent.agent_failure_context["explanation"]
    stale_finalized_turn = prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={"plan_hash": plan_hash, "candidate_graph_hash": candidate_hash},
    )
    assert not isinstance(stale_finalized_turn, dict)
    child_prepared = prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=child_turn,
        request_payload={"plan_hash": child_plan, "candidate_graph_hash": child_hash},
    )
    assert isinstance(child_prepared, dict)
    assert child_prepared["revision_id"] == child_transaction["revision_id"]
    assert compile_calls == [parent_revision]


def test_real_session_revision_scoped_monotonic_rollback(tmp_path) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import (
        _setup_v2_session_with_candidate,
        prepare_turn_transaction,
        read_state,
        rollback_turn_transaction,
    )

    root, session_id, turn_id, candidate_hash, _structural_hash, plan_hash = (
        _setup_v2_session_with_candidate(tmp_path)
    )
    transaction = _response_transaction(root, session_id, turn_id)
    pair_python = Path(transaction["bundle"]["python_path"])
    pair_sidecar = pair_python.with_suffix(".vibe.json")
    pair_before = (pair_python.read_bytes(), pair_sidecar.read_bytes() if pair_sidecar.is_file() else None)
    prepared = prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={"plan_hash": plan_hash, "candidate_graph_hash": candidate_hash},
    )
    assert isinstance(prepared, dict)
    generation_after_prepare = read_state(root / session_id)["next_generation"]
    unscoped = rollback_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": plan_hash,
            "generation": prepared["generation"],
            "lease_nonce": prepared["lease_nonce"],
        },
    )
    assert not isinstance(unscoped, dict)
    assert "exact prepared bundle revision" in unscoped.agent_failure_context["explanation"]
    mismatched = rollback_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": plan_hash,
            "generation": prepared["generation"],
            "lease_nonce": prepared["lease_nonce"],
            "revision_id": "0" * 64,
            "parent_revision": prepared["parent_revision"],
        },
    )
    assert not isinstance(mismatched, dict)
    assert "revision identity" in mismatched.agent_failure_context["explanation"]
    rolled = rollback_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": plan_hash,
            "generation": prepared["generation"],
            "lease_nonce": prepared["lease_nonce"],
            "revision_id": prepared["revision_id"],
            "parent_revision": prepared["parent_revision"],
        },
    )
    assert isinstance(rolled, dict), getattr(rolled, "agent_failure_context", repr(rolled))
    assert rolled["revision_id"] == prepared["revision_id"]
    assert rolled["parent_revision"] == prepared["parent_revision"]
    assert rolled["phase"] == "rollback_complete"
    state_after = read_state(root / session_id)
    assert state_after["next_generation"] >= generation_after_prepare
    assert (pair_python.read_bytes(), pair_sidecar.read_bytes() if pair_sidecar.is_file() else None) == pair_before


def test_real_session_untouched_sidecar_survives_capture_apply_rollback(tmp_path, monkeypatch) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import (
        _setup_v2_session_with_candidate,
        canonical_candidate_graph,
        finalize_turn_transaction,
        prepare_turn_transaction,
        rollback_turn_transaction,
    )
    from vibecomfy.security.provenance import Provenance
    from vibecomfy.workflow_bundle import load_bundle

    _stub_bundle_compile(monkeypatch)
    root, session_id, turn_id, candidate_hash, structural_hash, plan_hash = (
        _setup_v2_session_with_candidate(tmp_path)
    )
    transaction = _response_transaction(root, session_id, turn_id)
    python_path = Path(transaction["bundle"]["python_path"])
    sidecar_path = python_path.with_suffix(".vibe.json")
    assert sidecar_path.is_file()
    sidecar_before = sidecar_path.read_bytes()
    prepared = prepare_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={"plan_hash": plan_hash, "candidate_graph_hash": candidate_hash},
    )
    assert isinstance(prepared, dict)
    graph = canonical_candidate_graph(root, session_id, turn_id)
    finalized = finalize_turn_transaction(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        request_payload={
            "plan_hash": plan_hash,
            "generation": prepared["generation"],
            "lease_nonce": prepared["lease_nonce"],
            "post_apply_hash": structural_hash,
            "post_apply_graph": graph,
            "applied_delta_hash": prepared["candidate_transaction"]["plan"]["delta_hash"],
            "post_apply_hash_verified": True,
            "browser_verified": True,
        },
    )
    assert isinstance(finalized, dict), getattr(finalized, "agent_failure_context", repr(finalized))
    assert sidecar_path.read_bytes() == sidecar_before
    reopened = load_bundle(python_path, trust=Provenance.USER_CONFIRMED)
    assert reopened.revision_id == transaction["revision_id"]
    assert sidecar_path.read_bytes() == sidecar_before

    rollback_root, rollback_session, rollback_turn, rollback_hash, _structural, rollback_plan = (
        _setup_v2_session_with_candidate(tmp_path / "rollback")
    )
    rollback_transaction = _response_transaction(rollback_root, rollback_session, rollback_turn)
    rollback_sidecar = Path(rollback_transaction["bundle"]["python_path"]).with_suffix(".vibe.json")
    rollback_sidecar_before = rollback_sidecar.read_bytes()
    rollback_prepared = prepare_turn_transaction(
        session_root=rollback_root,
        session_id=rollback_session,
        turn_id=rollback_turn,
        request_payload={"plan_hash": rollback_plan, "candidate_graph_hash": rollback_hash},
    )
    assert isinstance(rollback_prepared, dict)
    rolled = rollback_turn_transaction(
        session_root=rollback_root,
        session_id=rollback_session,
        turn_id=rollback_turn,
        request_payload={
            "plan_hash": rollback_plan,
            "generation": rollback_prepared["generation"],
            "lease_nonce": rollback_prepared["lease_nonce"],
            "revision_id": rollback_prepared["revision_id"],
            "parent_revision": rollback_prepared["parent_revision"],
        },
    )
    assert isinstance(rolled, dict), getattr(rolled, "agent_failure_context", repr(rolled))
    assert rollback_sidecar.read_bytes() == rollback_sidecar_before
    load_bundle(Path(rollback_transaction["bundle"]["python_path"]), trust=Provenance.USER_CONFIRMED)
    assert rollback_sidecar.read_bytes() == rollback_sidecar_before


def test_real_session_publication_failure_keeps_prior_authority(tmp_path, monkeypatch) -> None:
    from tests.test_comfy_nodes_agent_backend_spine import _setup_v2_session_with_candidate
    from vibecomfy.comfy_nodes.agent import session as agent_session
    from vibecomfy.comfy_nodes.agent.candidate_transaction import CANDIDATE_TRANSACTION_FILENAME

    root, session_id, turn_id, _candidate_hash, _structural_hash, plan_hash = (
        _setup_v2_session_with_candidate(tmp_path)
    )
    prior_txn_dir = _txn_dir(root, session_id, turn_id, plan_hash)
    prior_python = prior_txn_dir / "candidate.py"
    prior_sidecar = prior_txn_dir / "candidate.vibe.json"
    prior_transaction = prior_txn_dir / CANDIDATE_TRANSACTION_FILENAME
    prior_receipt = (root / session_id / "turns" / turn_id / "authority" / "receipt.json").read_bytes()
    prior_pair = (prior_python.read_bytes(), prior_sidecar.read_bytes())
    prior_authority = prior_transaction.read_bytes()
    lifecycle = prior_txn_dir / "lifecycle_events.jsonl"
    lifecycle_before = lifecycle.read_bytes() if lifecycle.is_file() else None

    real_replace = agent_session.os.replace

    def fail_sidecar_publish(source, destination):
        if Path(destination).name == "candidate.vibe.json":
            raise OSError("injected sidecar publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(agent_session.os, "replace", fail_sidecar_publish)
    with pytest.raises(OSError, match="injected sidecar publication failure"):
        _record_v2_turn(
            tmp_path,
            root=root,
            session_id=session_id,
            label="v2-failed-publish",
        )

    failed_turns = sorted(
        path.name for path in (root / session_id / "turns").iterdir() if path.is_dir()
    )
    failed_turn = failed_turns[-1]
    assert failed_turn != turn_id
    failed_turn_dir = root / session_id / "turns" / failed_turn
    assert list(failed_turn_dir.rglob("candidate.py")) == []
    assert list(failed_turn_dir.rglob(CANDIDATE_TRANSACTION_FILENAME)) == []
    assert list(failed_turn_dir.rglob(".pending/candidate.py")) == []
    assert list(failed_turn_dir.rglob(".pending/candidate.vibe.json")) == []
    assert list(failed_turn_dir.rglob("finalized.json")) == []
    assert list(failed_turn_dir.rglob("lifecycle_events.jsonl")) == []
    assert list(failed_turn_dir.rglob("approval*.json")) == []
    assert list(failed_turn_dir.rglob("authority/receipt.json")) == []
    assert (prior_python.read_bytes(), prior_sidecar.read_bytes()) == prior_pair
    assert prior_transaction.read_bytes() == prior_authority
    assert (root / session_id / "turns" / turn_id / "authority" / "receipt.json").read_bytes() == prior_receipt
    assert (lifecycle.read_bytes() if lifecycle.is_file() else None) == lifecycle_before
    assert not (prior_txn_dir / "finalized.json").exists()
    assert not (prior_txn_dir / ".pending" / "candidate.py").exists()
