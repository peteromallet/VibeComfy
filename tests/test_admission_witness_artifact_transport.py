"""Admission witness custody from child response to offline intent judging.

This is a no-model regression for the late live-agentic path.  The fixture
mints a real durable response/receipt/candidate-transaction trio through the
production session writer, hands the child-shaped response to headless
artifact synthesis, removes the source session, and then invokes the real
intent judge over only the copied artifacts.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.live_agentic_harness.intent_judge import judge_edit_intent
from tests.live_agentic_harness.lineage_check import assess_artifact_lineage
from vibecomfy.agent.artifacts import synthesize_headless_artifacts
from vibecomfy.comfy_nodes.agent.artifact_lineage import (
    FALLBACK_REASONS,
    LINK_KINDS,
    build_artifact_lineage,
    fallback_row,
    primary_row,
)
from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    capture_ingress_schema_snapshot,
)
from vibecomfy.comfy_nodes.agent.session import (
    allocate_turn,
    record_idempotent_response,
    structural_graph_hash,
    v2_mutation_plan_hash,
)
from vibecomfy.executor.contracts import ExecutorResult
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ImplementationResult,
)
from vibecomfy.schema import FrozenSchemaSnapshotProvider, InputSpec, NodeSchema


_CLASS_TYPE = "AdmissionWitnessOnlyCarrier"
_WORKFLOW_ID = "123e4567-e89b-12d3-a456-426614174000"
_SCENARIO = {
    "id": "admission-witness-copy",
    "query": "set strength to 30",
    "assessment": {"expect_graph_changed": True},
}


class _AdmissionProvider:
    def __init__(self) -> None:
        self._schema = NodeSchema(
            class_type=_CLASS_TYPE,
            pack="test-only-admission",
            inputs={"strength": InputSpec("INT", required=True)},
            outputs=[],
        )

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schema if class_type == _CLASS_TYPE else None

    def schemas(self) -> dict[str, NodeSchema]:
        return {_CLASS_TYPE: self._schema}


def _ui(value: int) -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": _CLASS_TYPE,
                "properties": {"vibecomfy_uid": "carrier"},
                "widgets_values": [value],
            }
        ],
        "links": [],
        "last_node_id": 1,
        "last_link_id": 0,
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }


def _lineage(session_id: str, turn_id: str, *, landed: bool = True) -> dict:
    primary_kinds = {"accepted_delta", "candidate", "replay_proof"} if landed else set()
    return build_artifact_lineage(
        lineage={
            "scenario_id": _SCENARIO["id"],
            "session_id": session_id,
            "turn_id": turn_id,
            "baseline_id": "0000",
        },
        rows=[
            primary_row(kind, "a" * 64)
            if kind in primary_kinds
            else fallback_row(kind, sorted(FALLBACK_REASONS[kind])[0])
            for kind in LINK_KINDS
        ],
    )


def _mint_child_and_copy(tmp_path: Path, *, session_id: str) -> tuple[Path, Path, str]:
    source_root = tmp_path / "source-sessions"
    pre = _ui(20)
    post = _ui(30)
    request = {
        "task": _SCENARIO["query"],
        "workflow_id": _WORKFLOW_ID,
        "graph": pre,
    }
    allocation = allocate_turn(
        session_root=source_root,
        session_id=session_id,
        request_payload=request,
    )
    turn_id = str(allocation.context.turn_id)
    (allocation.turn_dir / "request.json").write_text(
        json.dumps(request), encoding="utf-8"
    )
    (allocation.turn_dir / "original.ui.json").write_text(
        json.dumps(pre), encoding="utf-8"
    )
    (allocation.turn_dir / "candidate.ui.json").write_text(
        json.dumps(post), encoding="utf-8"
    )
    delta = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "carrier", "strength"],
                "value": 30,
            }
        ],
    }
    plan_hash = v2_mutation_plan_hash(
        delta_ops_envelope=delta,
        structural_hash_before=structural_graph_hash(pre),
        structural_hash_after=structural_graph_hash(post),
    )
    snapshot = capture_ingress_schema_snapshot(
        schema_provider=_AdmissionProvider(), graph=pre
    )
    persisted_response = {
        "ok": True,
        "route": "revise",
        "session_id": session_id,
        "turn_id": turn_id,
        "graph": post,
        "candidate_graph": post,
        "candidate": {
            "graph": post,
            "plan_hash": plan_hash,
            "structural_hash_before": structural_graph_hash(pre),
            "structural_hash_after": structural_graph_hash(post),
        },
        "graph_unchanged": False,
        "change_details": {"landed_operation_count": 1},
        "gates": {"queue_validate_ok": True},
        "eligibility": {"applyable": True},
        "agent_edit_protocol": "v2_delta",
        "accepted_batch": [{"op": op} for op in delta["ops"]],
    }
    record_idempotent_response(
        session_root=source_root,
        session_id=session_id,
        scope="edit",
        idempotency_key=None,
        request_hash=allocation.request_hash,
        response=persisted_response,
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
        schema_provider=FrozenSchemaSnapshotProvider(snapshot),
    )

    # This is the deliberately lossy child projection seen in r5: it has the
    # accepted delta and durable identities, but no embedded receipt/transaction
    # and no detail/session path.  Its artifact paths still identify the real
    # child turn and are the transport handoff.
    child_response = {
        **persisted_response,
        "candidate": post,
        "artifacts": {
            "original_ui": str(allocation.turn_dir / "original.ui.json"),
            "candidate_ui": str(allocation.turn_dir / "candidate.ui.json"),
        },
        "report": {"executor": {"artifact_lineage": _lineage(session_id, turn_id)}},
    }
    output_dir = tmp_path / "child-output"
    synthesize_headless_artifacts(
        request=request,
        result=ExecutorResult.success(graph=post, reply="updated"),
        response=child_response,
        output_dir=output_dir,
        status="success",
        entrypoint="live_agentic_harness",
    )
    (output_dir / "artifact_lineage.json").write_text(
        json.dumps(_lineage(session_id, turn_id)), encoding="utf-8"
    )
    return output_dir, source_root, plan_hash


def _offline_verdict(
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    calls: list[dict] = []

    def _fake_model_turn(_task: str, **kwargs: object) -> dict:
        calls.append(json.loads(kwargs["messages"][1]["content"]))  # type: ignore[index]
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": True,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "The accepted delta performs the requested edit.",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn", _fake_model_turn
    )
    response = json.loads((output_dir / "response.json").read_text(encoding="utf-8"))
    verdict = judge_edit_intent(
        output_dir,
        _SCENARIO,
        response_snapshot=response,
    )
    verdict["_model_payloads"] = calls
    return verdict


class TestAdmissionWitnessArtifactTransport:
    def test_envelope_manifest_uses_executor_report_not_top_level_field(self) -> None:
        from tests.live_agentic_harness.lineage_check import _envelope_manifest

        manifest = _lineage("envelope-scope", "0001")
        assert _envelope_manifest({"artifact_lineage": manifest}) is None
        assert _envelope_manifest(
            {"report": {"executor": {"artifact_lineage": manifest}}}
        ) == manifest

    def test_executor_envelope_survives_child_copy_and_correlates_lineage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, source_root, _plan_hash = _mint_child_and_copy(
            tmp_path, session_id="envelope-terminal"
        )
        shutil.rmtree(source_root)

        reloaded = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        executor = reloaded["report"]["executor"]
        assert isinstance(executor["artifact_lineage"], dict)
        lineage = assess_artifact_lineage(output_dir, reloaded, _SCENARIO)
        assert lineage["provenance"] == "sidecar_correlated", lineage
        assert not any(
            issue["severity"] in {"error", "undetermined"}
            for issue in lineage["issues"]
        ), lineage

        verdict = _offline_verdict(output_dir, monkeypatch)
        assert verdict["pass_"] is True, verdict
        assert verdict["metadata"]["schema_witness_resolution"]["status"] == (
            "consumed"
        )

    def test_no_candidate_executor_envelope_survives_child_copy_and_reloads(
        self, tmp_path: Path
    ) -> None:
        session_id = "no-candidate-envelope"
        turn_id = "0001"
        source_root = tmp_path / "source-no-candidate"
        turn_dir = source_root / session_id / "turns" / turn_id
        turn_dir.mkdir(parents=True)
        request = {"query": "Which output should I use?", "graph": _ui(20)}
        child_response = {
            "ok": True,
            "route": "clarify",
            "session_id": session_id,
            "turn_id": turn_id,
            "terminal_state": "no_candidate",
            "graph_unchanged": True,
            "outcome": {
                "kind": "clarify",
                "question": "Which output should I use?",
            },
        }
        (turn_dir / "response.json").write_text(
            json.dumps(child_response), encoding="utf-8"
        )
        manifest = _lineage(session_id, turn_id, landed=False)
        executor_envelope = {
            **child_response,
            "detail_json_path": str(turn_dir / "response.json"),
            "report": {"executor": {"artifact_lineage": manifest}},
        }
        output_dir = tmp_path / "no-candidate-output"
        synthesize_headless_artifacts(
            request=request,
            result=ExecutorResult.success(graph=_ui(20), reply="Need input."),
            response=executor_envelope,
            output_dir=output_dir,
            status="success",
            entrypoint="test",
        )
        (output_dir / "artifact_lineage.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        shutil.rmtree(source_root)

        reloaded = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        assert reloaded["outcome"] == executor_envelope["outcome"]
        assert reloaded["report"]["executor"]["artifact_lineage"] == manifest
        lineage = assess_artifact_lineage(output_dir, reloaded, {"id": _SCENARIO["id"]})
        assert lineage["provenance"] == "sidecar_correlated", lineage
        assert lineage["issues"] == []

    def test_lineage_schema_row_uses_the_bound_admission_witness(
        self, tmp_path: Path
    ) -> None:
        from vibecomfy.comfy_nodes.agent.artifact_lineage import (
            canonical_lineage_digest,
        )
        from vibecomfy.executor import core

        output_dir, source_root, _plan_hash = _mint_child_and_copy(
            tmp_path, session_id="lineage-bound-witness"
        )
        shutil.rmtree(source_root)
        durable = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        copied_turn = Path(durable["detail_json_path_resolved"]).parent
        receipt = json.loads(
            (copied_turn / "authority" / "receipt.json").read_text(
                encoding="utf-8"
            )
        )

        rows = core._artifact_lineage_rows(
            ExecutorRequest(query=_SCENARIO["query"], graph=_ui(20)),
            plan=ClassifyDecision(
                intent="edit", route="revise", implement=True, reply=True
            ),
            research=None,
            implementation_result=ImplementationResult(
                graph=_ui(30), message="updated", durable_response=durable
            ),
            model_attempts=(),
            orchestration_mode="staged",
        )
        schema_row = next(row for row in rows if row["kind"] == "schema_snapshot")
        assert schema_row["row_class"] == "primary"
        assert schema_row["digest"] == canonical_lineage_digest(
            receipt["schema_witness"]
        )

    def test_lineage_schema_row_rejects_foreign_envelope_identity(
        self, tmp_path: Path
    ) -> None:
        from vibecomfy.executor import core

        output_dir, source_root, _plan_hash = _mint_child_and_copy(
            tmp_path, session_id="lineage-current-envelope"
        )
        shutil.rmtree(source_root)
        durable = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )

        # The copied receipt/transaction remain a valid pair at their durable
        # path.  Only the current executor envelope is changed to identify a
        # different response; that foreign pair must not authorize its schema
        # lineage row.
        durable["session_id"] = "lineage-foreign-envelope"
        durable["turn_id"] = "0099"
        rows = core._artifact_lineage_rows(
            ExecutorRequest(query=_SCENARIO["query"], graph=_ui(20)),
            plan=ClassifyDecision(
                intent="edit", route="revise", implement=True, reply=True
            ),
            research=None,
            implementation_result=ImplementationResult(
                graph=_ui(30), message="updated", durable_response=durable
            ),
            model_attempts=(),
            orchestration_mode="staged",
        )

        schema_row = next(row for row in rows if row["kind"] == "schema_snapshot")
        assert schema_row["row_class"] == "fallback"
        assert schema_row["reason"] == "no_schema_witness"
        assert schema_row["detail"] == {
            "binding_error": "durable_turn_path_identity_mismatch"
        }

    def test_lineage_schema_row_rejects_foreign_envelope_selected_plan(
        self, tmp_path: Path
    ) -> None:
        from vibecomfy.executor import core

        output_dir, source_root, plan_hash = _mint_child_and_copy(
            tmp_path, session_id="lineage-current-plan"
        )
        shutil.rmtree(source_root)
        durable = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        assert durable["plan_hash"] == plan_hash

        # Only the executor envelope's selected plan changes.  The copied
        # source response and its valid receipt/transaction pair still select
        # the original plan and must not be used to override this conflict.
        durable["plan_hash"] = "f" * 64
        rows = core._artifact_lineage_rows(
            ExecutorRequest(query=_SCENARIO["query"], graph=_ui(20)),
            plan=ClassifyDecision(
                intent="edit", route="revise", implement=True, reply=True
            ),
            research=None,
            implementation_result=ImplementationResult(
                graph=_ui(30), message="updated", durable_response=durable
            ),
            model_attempts=(),
            orchestration_mode="staged",
        )

        schema_row = next(row for row in rows if row["kind"] == "schema_snapshot")
        assert schema_row["row_class"] == "fallback"
        assert schema_row["reason"] == "no_schema_witness"
        assert schema_row["detail"] == {
            "binding_error": "current_envelope_selected_plan_contradiction"
        }

    def test_foreign_turn_lineage_sidecar_still_fails_closed(
        self, tmp_path: Path
    ) -> None:
        output_dir, source_root, _plan_hash = _mint_child_and_copy(
            tmp_path, session_id="lineage-original-turn"
        )
        shutil.rmtree(source_root)
        (output_dir / "artifact_lineage.json").write_text(
            json.dumps(_lineage("lineage-foreign-turn", "0001")),
            encoding="utf-8",
        )
        response = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )

        result = assess_artifact_lineage(output_dir, response, _SCENARIO)

        assert any(
            issue["severity"] in {"error", "undetermined"}
            for issue in result["issues"]
        ), result

    def test_sidecar_without_executor_envelope_still_fails_closed(
        self, tmp_path: Path
    ) -> None:
        output_dir, source_root, _plan_hash = _mint_child_and_copy(
            tmp_path, session_id="lineage-absent-envelope"
        )
        shutil.rmtree(source_root)
        response = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        response["report"]["executor"].pop("artifact_lineage")

        result = assess_artifact_lineage(output_dir, response, _SCENARIO)

        assert any(
            issue["severity"] in {"error", "undetermined"}
            for issue in result["issues"]
        ), result

    def test_tampered_lineage_manifest_still_fails_closed(
        self, tmp_path: Path
    ) -> None:
        output_dir, source_root, _plan_hash = _mint_child_and_copy(
            tmp_path, session_id="lineage-tampered-manifest"
        )
        shutil.rmtree(source_root)
        manifest_path = output_dir / "artifact_lineage.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["rows"][0]["digest"] = "f" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        response = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )

        result = assess_artifact_lineage(output_dir, response, _SCENARIO)

        assert any(
            issue["severity"] in {"error", "undetermined"}
            for issue in result["issues"]
        ), result

    def test_original_admission_witness_survives_child_copy_and_is_consumed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, source_root, plan_hash = _mint_child_and_copy(
            tmp_path, session_id="witness-valid"
        )
        response = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        copied_turn = Path(response["detail_json_path_resolved"]).parent
        assert copied_turn.is_relative_to(output_dir)
        assert copied_turn.parts[-3:] == ("witness-valid", "turns", "0001")
        assert (copied_turn / "authority" / "receipt.json").is_file()
        assert (
            copied_turn / "transactions" / plan_hash / "candidate_transaction.json"
        ).is_file()
        copied_receipt = json.loads(
            (copied_turn / "authority" / "receipt.json").read_text(encoding="utf-8")
        )

        shutil.rmtree(source_root)
        verdict = _offline_verdict(output_dir, monkeypatch)

        assert verdict["pass_"] is True, verdict
        assert verdict["metadata"]["schema_witness_resolution"]["status"] == "consumed"
        assert (
            verdict["metadata"]["schema_witness_resolution"]["witness_hash"]
            == copied_receipt["schema_witness"]["witness_hash"]
        )
        payload = verdict["_model_payloads"][0]
        assert payload["delta_replay"]["verified"] is True
        assert payload["named_fields"]["carrier"]["strength"] == 30

    def test_absent_witness_fails_closed_with_resolution_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, source_root, _plan_hash = _mint_child_and_copy(
            tmp_path, session_id="witness-absent"
        )
        response = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        copied_turn = Path(response["detail_json_path_resolved"]).parent
        receipt_path = copied_turn / "authority" / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.pop("schema_witness")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        shutil.rmtree(source_root)

        verdict = _offline_verdict(output_dir, monkeypatch)

        assert verdict["pass_"] is False
        resolution = verdict["metadata"]["schema_witness_resolution"]
        assert resolution["status"] == "rejected"
        assert resolution["reason"].startswith("invalid_authority_receipt:")
        assert "missing_touched_schema" in verdict["rationale"]
        assert verdict["_model_payloads"] == []

    def test_tampered_binding_fails_closed_with_resolution_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, source_root, plan_hash = _mint_child_and_copy(
            tmp_path, session_id="witness-tampered"
        )
        response = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        copied_turn = Path(response["detail_json_path_resolved"]).parent
        transaction_path = (
            copied_turn / "transactions" / plan_hash / "candidate_transaction.json"
        )
        transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
        transaction["candidate_authority"]["authority_receipt_digest"] = "f" * 64
        transaction["hashes"]["authority_receipt_hash"] = "f" * 64
        transaction_path.write_text(json.dumps(transaction), encoding="utf-8")
        shutil.rmtree(source_root)

        verdict = _offline_verdict(output_dir, monkeypatch)

        assert verdict["pass_"] is False
        assert verdict["metadata"]["schema_witness_resolution"] == {
            "status": "rejected",
            "reason": "authority_receipt_digest_mismatch",
        }
        assert "missing_touched_schema" in verdict["rationale"]
        assert verdict["_model_payloads"] == []

    def test_missing_snapshot_and_catalog_never_reconstructs_from_candidate_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, source_root, _plan_hash = _mint_child_and_copy(
            tmp_path, session_id="witness-no-authority"
        )
        response = json.loads(
            (output_dir / "response.json").read_text(encoding="utf-8")
        )
        copied_turn = Path(response["detail_json_path_resolved"]).parent
        shutil.rmtree(copied_turn / "authority")
        shutil.rmtree(source_root)

        verdict = _offline_verdict(output_dir, monkeypatch)

        assert verdict["pass_"] is False
        assert verdict["metadata"]["schema_witness_resolution"] == {
            "status": "rejected",
            "reason": "missing_durable_turn",
        }
        assert "missing_touched_schema" in verdict["rationale"]
        assert verdict["_model_payloads"] == []
