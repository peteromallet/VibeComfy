from __future__ import annotations

from pathlib import Path

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    _response_claims_applyable,
    build_and_persist_authority_receipt,
    build_authority_receipt,
    verify_replay,
)
from vibecomfy.porting.edit.ops import canonical_op_to_dict
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _single_widget_graph(class_type: str, *, uid: str = "133") -> dict:
    return {
        "last_node_id": int(uid),
        "last_link_id": 0,
        "nodes": [
            {
                "id": int(uid),
                "type": class_type,
                "pos": [0, 0],
                "size": [240, 120],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {"vibecomfy_uid": uid},
                "widgets_values": ["old prompt"],
            }
        ],
        "links": [],
        "groups": [],
        "config": {},
        "extra": {},
    }


def test_qwen_positional_assignment_seals_named_delta_and_frozen_replay_succeeds() -> (
    None
):
    class_type = "TextEncodeQwenImageEditPlus"
    provider = _Provider(
        {
            class_type: NodeSchema(
                class_type=class_type,
                pack="ComfyUI-QwenImageWrapper",
                inputs={
                    "prompt": InputSpec(
                        type="STRING",
                        required=True,
                        default="",
                    )
                },
                outputs=[OutputSpec(type="CONDITIONING", name="CONDITIONING")],
            )
        }
    )
    submit_graph = _single_widget_graph(class_type)
    submit_graph["last_node_id"] = 200
    submit_graph["nodes"].append(
        {
            "id": 200,
            "type": "UntouchedUnknownNode",
            "pos": [320, 0],
            "size": [160, 80],
            "flags": {},
            "order": 1,
            "mode": 0,
            "inputs": [],
            "outputs": [],
            "properties": {"vibecomfy_uid": "200"},
            "widgets_values": [],
        }
    )
    session = EditSession(submit_graph, schema_provider=provider)

    result = session.apply_batch(
        "textencodeqwenimageeditplus.widget_0 = 'make the coat bright red'"
    )

    assert result.ok is True
    assert len(result.landed_ops) == 1
    op = canonical_op_to_dict(result.landed_ops[0])
    assert op["target"] == ["", "133", "prompt"]
    assert "widget_0" not in repr(op)

    accepted_batch = [{"statement_index": 1, "op": op}]
    envelope = {"schema_version": "2.0.0", "ops": [op]}
    receipt = build_authority_receipt(
        session_id="qwen-canonical",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=session.working_ui,
        response={
            "accepted_batch": accepted_batch,
            "apply_eligible": True,
            "outcome": {"kind": "candidate"},
        },
        schema_version="2.0.0",
        schema_provider=provider,
    )

    assert receipt.schema_witness is not None
    # An untouched schema-less neighbor is carried byte-for-byte and does not
    # block the named Qwen edit; only missing *touched* schemas fail closed.
    assert receipt.schema_witness["missing_class_types"] == ["UntouchedUnknownNode"]
    assert receipt.replay.replay_ok is True
    assert receipt.replay.candidate_matches is True
    assert receipt.is_applyable is True


def test_unresolved_positional_widget_is_rejected_before_delta_is_sealed() -> None:
    session = EditSession(
        _single_widget_graph("IndexTTSEmotionOptionsNode", uid="125"),
        schema_provider=_Provider({}),
    )

    result = session.apply_batch(
        "indexttsemotionoptionsnode.widget_0 = 'cannot be named honestly'"
    )

    assert result.ok is False
    assert result.landed_ops == ()
    assert result.statements[0].reason == "widget_unknown"
    assert result.statements[0].diagnostics[0].code == "widget_unknown"


def test_missing_touched_schema_rejects_candidate_and_replaces_success_narration(
    tmp_path: Path,
) -> None:
    class_type = "LayerMask: SegmentAnythingUltra V3"
    submit_graph = _single_widget_graph(class_type, uid="34")
    candidate = _single_widget_graph(class_type, uid="34")
    candidate["nodes"][0]["widgets_values"] = ["person"]
    op = {
        "op": "set_node_field",
        "target": ["", "34", "prompt"],
        "value": "person",
    }
    accepted_batch = [{"statement_index": 1, "op": op}]
    response = {
        "message": "Done — I changed the segmentation prompt.",
        "graph": candidate,
        "candidate": {"state": "candidate_ready", "graph": candidate},
        "accepted_batch": accepted_batch,
        "agent_edit_protocol": "v2_delta",
        "apply_eligible": True,
        "canvas_apply_allowed": True,
        "queue_allowed": True,
        "eligibility": {"applyable": True, "reason": "applyable"},
        "apply_eligibility": {"applyable": True, "reason": "applyable"},
        "outcome": {"kind": "candidate", "changes": []},
    }

    receipt, stamped = build_and_persist_authority_receipt(
        turn_dir=tmp_path / "turns" / "0001",
        session_id="missing-schema",
        turn_id="0001",
        request_payload={"graph": submit_graph},
        response=response,
        schema_version="2.0.0",
        schema_provider=_Provider({}),
    )

    assert receipt.replay.replay_ok is False
    assert receipt.replay.error == f"missing_touched_schema:{class_type}"
    assert receipt.is_applyable is False
    assert stamped["apply_eligible"] is False
    assert stamped["eligibility"]["applyable"] is False
    assert stamped["apply_eligibility"]["applyable"] is False
    assert stamped["apply_eligibility"]["reason"] == "authority_replay_mismatch"
    assert stamped["graph_unchanged"] is True
    assert stamped["no_candidate_reason"] == "authority_replay_mismatch"
    assert stamped["schema_witness_error"] == {
        "code": "missing_touched_schema",
        "class_types": [class_type],
    }
    assert stamped["outcome"]["kind"] == "clarify"
    assert "schema evidence is unavailable" in stamped["message"]
    assert stamped["candidate"]["state"] == "rejected"
    assert stamped["accepted_batch"] == accepted_batch
    assert stamped["graph"] == candidate


def test_prompt_wrapped_api_graph_cannot_evade_missing_touched_schema_gate() -> None:
    class_type = "IndexTTSEngineNode"
    submit_graph = {
        "prompt": {
            "138": {
                "class_type": class_type,
                "inputs": {"widget_0": "local:IndexTTS-2"},
            }
        }
    }
    candidate = {
        "prompt": {
            "138": {
                "class_type": class_type,
                "inputs": {"widget_0": "different"},
            }
        }
    }
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "138", "model_version"],
                "value": "different",
            }
        ],
    }

    receipt = build_authority_receipt(
        session_id="wrapped-api-missing-schema",
        turn_id="0001",
        submit_graph=submit_graph,
        cumulative_delta_envelope=envelope,
        candidate=candidate,
        response={"apply_eligible": True, "outcome": {"kind": "candidate"}},
        schema_version="2.0.0",
        schema_provider=_Provider({}),
    )

    assert receipt.schema_witness is not None
    assert receipt.schema_witness["missing_class_types"] == [class_type]
    assert receipt.replay.replay_ok is False
    assert receipt.replay.error == f"missing_touched_schema:{class_type}"
    assert receipt.is_applyable is False


def test_replay_still_rejects_a_candidate_hash_mismatch() -> None:
    submit_graph = _single_widget_graph("KnownPromptNode")
    provider = _Provider(
        {
            "KnownPromptNode": NodeSchema(
                class_type="KnownPromptNode",
                pack="test",
                inputs={"prompt": InputSpec(type="STRING", required=True)},
                outputs=[],
            )
        }
    )
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "133", "prompt"],
                "value": "authoritative value",
            }
        ],
    }
    tampered = _single_widget_graph("KnownPromptNode")
    tampered["nodes"][0]["widgets_values"] = ["different value"]

    replay = verify_replay(
        submit_graph,
        envelope,
        tampered,
        schema_provider=provider,
    )

    assert replay.replay_ok is True
    assert replay.candidate_matches is False
    assert replay.error == "candidate_hash_mismatch"


def test_generic_replay_mismatch_replaces_success_and_retains_audit_evidence(
    tmp_path: Path,
) -> None:
    """A nested-only apply claim cannot preserve a false success envelope."""
    class_type = "KnownPromptNode"
    provider = _Provider(
        {
            class_type: NodeSchema(
                class_type=class_type,
                pack="test",
                inputs={"prompt": InputSpec(type="STRING", required=True)},
                outputs=[],
            )
        }
    )
    submit_graph = _single_widget_graph(class_type)
    tampered_candidate = _single_widget_graph(class_type)
    tampered_candidate["nodes"][0]["widgets_values"] = ["not the accepted value"]
    op = {
        "op": "set_node_field",
        "target": ["", "133", "prompt"],
        "value": "authoritative value",
    }
    accepted_batch = [{"statement_index": 1, "op": op}]
    response = {
        "message": "Done — I changed the prompt.",
        "graph": tampered_candidate,
        "candidate": {
            "state": "candidate_ready",
            "graph": tampered_candidate,
        },
        "accepted_batch": accepted_batch,
        "agent_edit_protocol": "v2_delta",
        # This is intentionally the only true applyability claim.
        "apply_eligibility": {"applyable": True, "reason": "applyable"},
        "outcome": {"kind": "candidate", "changes": ["prompt"]},
    }

    assert _response_claims_applyable(response) is True
    receipt, stamped = build_and_persist_authority_receipt(
        turn_dir=tmp_path / "turns" / "0001",
        session_id="generic-replay-mismatch",
        turn_id="0001",
        request_payload={"graph": submit_graph},
        response=response,
        schema_version="2.0.0",
        schema_provider=provider,
    )

    assert receipt.replay.replay_ok is True
    assert receipt.replay.candidate_matches is False
    assert receipt.replay.error == "candidate_hash_mismatch"
    assert receipt.is_applyable is False
    for field in (
        "canvas_apply_allowed",
        "queue_allowed",
        "apply_allowed",
        "apply_eligible",
    ):
        assert stamped[field] is False
    assert stamped["eligibility"]["applyable"] is False
    assert stamped["apply_eligibility"]["applyable"] is False
    assert stamped["graph_unchanged"] is True
    assert stamped["outcome"]["kind"] == "clarify"
    assert stamped["internal_outcome"]["kind"] == "clarify"
    assert "replay verification failed" in stamped["message"]
    assert "changed the prompt" not in stamped["message"]
    # Rejected candidate and accepted delta are retained for immutable audit.
    assert stamped["candidate"]["state"] == "rejected"
    assert stamped["candidate"]["graph"] == tampered_candidate
    assert stamped["graph"] == tampered_candidate
    assert stamped["accepted_batch"] == accepted_batch
