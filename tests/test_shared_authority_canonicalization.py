from __future__ import annotations

import ast
import copy
import json
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


_R5_FIXTURES = Path(__file__).parent / "fixtures" / "workflow_execution_spine_r5"


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


def test_set_node_field_lowers_mixed_qwen_widget_alias_once_and_changes_candidate() -> None:
    """A UI/API mixed node must not lower one prompt slot twice.

    Some cloud Qwen payloads retain both the named ``prompt`` input and its
    positional ``widget_0`` carrier.  The field edit is one logical change;
    lowering it must update both retained aliases and emit one Python kwarg.
    """
    from vibecomfy.porting.edit._ir_utils import apply_edit_cow
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python
    from vibecomfy.porting.emit.ui import emit_ui_json
    from vibecomfy.workflow import RawWidgetPayload, VibeNode, VibeWorkflow, WorkflowSource

    class_type = "TextEncodeQwenImageEditPlus"
    provider = _Provider(
        {
            class_type: NodeSchema(
                class_type=class_type,
                pack="ComfyUI-QwenImageWrapper",
                inputs={"prompt": InputSpec(type="STRING", required=True)},
                outputs=[],
            )
        }
    )
    workflow = VibeWorkflow("qwen-mixed-widget", WorkflowSource("test"))
    workflow.nodes["133"] = VibeNode(
        id="133",
        class_type=class_type,
        uid="133",
        inputs={"prompt": "old"},
        widgets={"widget_0": "old"},
        raw_widgets=RawWidgetPayload(
            values=["old"],
            shape="list",
            source="ui.widgets_values",
            has_dict_rows=False,
            length=1,
        ),
        metadata={"_ui": {"id": 133, "type": class_type, "widgets_values": ["old"]}},
    )

    edited = apply_edit_cow(
        workflow,
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget("", "133", "prompt"),
            value="new",
        ),
        schema_provider=provider,
    )
    node = edited.nodes["133"]
    assert node.inputs["prompt"] == "new"
    assert node.widgets["widget_0"] == "new"

    source = emit_agent_edit_python(edited)
    call = next(item for item in ast.walk(ast.parse(source)) if isinstance(item, ast.Call))
    assert [keyword.arg for keyword in call.keywords if keyword.arg is not None] == ["prompt"]
    assert "prompt_2" not in source
    assert "prompt='new'" in source

    candidate = emit_ui_json(edited, schema_provider=provider)
    assert candidate is not None
    assert candidate["nodes"][0]["widgets_values"] == ["new"]


def test_r5_tts_schema_remains_visible_from_an_isolated_fixture_copy(
    tmp_path: Path,
) -> None:
    fixture_path = _R5_FIXTURES / "tts_schema_visibility.json"
    isolated_fixture = tmp_path / fixture_path.name
    isolated_fixture.write_bytes(fixture_path.read_bytes())
    fixture = json.loads(isolated_fixture.read_text(encoding="utf-8"))
    schema = fixture["schema"]
    class_type = schema["class_type"]
    provider = _Provider(
        {
            class_type: NodeSchema(
                class_type=class_type,
                pack=schema["pack"],
                inputs={
                    "emotion_control": InputSpec(
                        type="STRING",
                        required=False,
                        default="neutral",
                    )
                },
                outputs=[
                    OutputSpec(type="EMOTION_OPTIONS", name="EMOTION_OPTIONS")
                ],
            )
        }
    )

    result = EditSession(
        _single_widget_graph(class_type, uid="1"),
        schema_provider=provider,
    ).apply_batch(fixture["operation"]["statement"])

    assert result.ok is True
    assert result.landed_ops
    assert fixture["expected"] == {
        "schema_visible": True,
        "provider": "authoritative_object_info",
        "operation": "accepted",
    }


def test_r5_missing_touched_layermask_preserves_untouched_unknown_fixture(
    tmp_path: Path,
) -> None:
    fixture = json.loads(
        (_R5_FIXTURES / "missing_touched_layermask.json").read_text(
            encoding="utf-8"
        )
    )
    submit_graph = fixture["graph"]
    candidate = copy.deepcopy(submit_graph)
    candidate["nodes"][0]["widgets_values"] = [fixture["operation"]["value"]]
    operation = {
        "op": "set_node_field",
        "target": fixture["operation"]["target"],
        "value": fixture["operation"]["value"],
    }
    receipt, stamped = build_and_persist_authority_receipt(
        turn_dir=tmp_path / "turns" / "0001",
        session_id="r5-missing-touched-schema",
        turn_id="0001",
        request_payload={"graph": submit_graph},
        response={
            "message": "changed",
            "graph": candidate,
            "candidate": {"state": "candidate_ready", "graph": candidate},
            "accepted_batch": [{"statement_index": 1, "op": operation}],
            "agent_edit_protocol": "v2_delta",
            "apply_eligible": True,
            "canvas_apply_allowed": True,
            "queue_allowed": True,
            "eligibility": {"applyable": True, "reason": "applyable"},
            "apply_eligibility": {"applyable": True, "reason": "applyable"},
            "outcome": {"kind": "candidate", "changes": []},
        },
        schema_version="2.0.0",
        schema_provider=_Provider({}),
    )

    assert receipt.replay.replay_ok is False
    assert receipt.replay.error == fixture["expected"]["error"]
    assert receipt.is_applyable is False
    # Row 4 contract: the rejected product is audit-only; public keys must
    # not carry it.  The untouched unknown neighbor survives byte-for-byte.
    assert stamped["audit"]["rejected_candidate"]["state"] == "rejected"
    assert stamped["audit"]["rejected_candidate"]["graph"]["nodes"][1] == candidate["nodes"][1]
    assert "candidate" not in stamped and "graph" not in stamped


def test_r5_persisted_replay_fixture_has_success_and_mismatch_paths() -> None:
    fixture = json.loads(
        (_R5_FIXTURES / "replay_mismatch_and_success.json").read_text(
            encoding="utf-8"
        )
    )
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
        "ops": [fixture["operation"]],
    }

    successful = verify_replay(
        fixture["submit_graph"],
        envelope,
        fixture["candidate_success"],
        schema_provider=provider,
    )
    mismatch = verify_replay(
        fixture["submit_graph"],
        envelope,
        fixture["candidate_mismatch"],
        schema_provider=provider,
    )

    assert {
        "replay_ok": successful.replay_ok,
        "candidate_matches": successful.candidate_matches,
    } == fixture["expected"]["success"]
    assert {
        "replay_ok": mismatch.replay_ok,
        "candidate_matches": mismatch.candidate_matches,
        "error": mismatch.error,
    } == fixture["expected"]["mismatch"]


def test_positional_widget_seals_via_shipped_schema_and_reports_old_unresolved() -> None:
    """Contract evolution note (R1BR-001 follow-on): the shipped
    authoritative object_info cache resolves IndexTTSEmotionOptionsNode's
    positional widget_0, so the statement seals a named delta and surfaces an
    explicit old-unresolved diagnostic instead of failing the batch as
    widget_unknown.  Fail-closed enforcement for unverifiable products stays
    with the authority-receipt replay gate."""
    session = EditSession(
        _single_widget_graph("IndexTTSEmotionOptionsNode", uid="125"),
        schema_provider=_Provider({}),
    )

    result = session.apply_batch(
        "indexttsemotionoptionsnode.widget_0 = 'cannot be named honestly'"
    )

    assert result.ok is True
    assert len(result.landed_ops) == 1
    assert result.landed_ops[0].target.field_path == "emotion_control"
    diagnostic = result.statements[0].diagnostics[0]
    assert diagnostic.code == "field_change_old_unresolved"
    assert diagnostic.detail == {"uid": "125", "field_path": "emotion_control"}


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
    assert stamped["eligibility"]["reason"] == "authority_rejected"
    assert stamped["terminal_reason"] == "authority_rejected"
    assert stamped["graph_unchanged"] is True
    assert stamped["no_candidate_reason"] == "authority_replay_mismatch"
    assert stamped["schema_witness_error"] == {
        "code": "missing_touched_schema",
        "class_types": [class_type],
    }
    # Never let a replay mismatch masquerade as clarify/candidate on the wire.
    assert stamped["outcome"]["kind"] == "error"
    assert stamped["outcome"]["failure_kind"] == "SchemaGap"
    assert "schema evidence is unavailable" in stamped["message"]
    # Row 4: rejected product is audit-only; public keys must not carry it.
    rejected_candidate = stamped["audit"]["rejected_candidate"]
    assert rejected_candidate["state"] == "rejected"
    assert rejected_candidate["graph"] == candidate
    assert "candidate" not in stamped
    assert "graph" not in stamped
    assert "accepted_batch" not in stamped


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
    # Never let a replay mismatch masquerade as clarify on the public wire.
    assert stamped["outcome"]["kind"] == "error"
    assert stamped["outcome"]["failure_kind"] == "ValidationError"
    assert "replay verification failed" in stamped["message"]
    assert "changed the prompt" not in stamped["message"]
    # Row 4: the rejected product survives as immutable audit evidence only.
    rejected_candidate = stamped["audit"]["rejected_candidate"]
    assert rejected_candidate["state"] == "rejected"
    assert rejected_candidate["graph"] == tampered_candidate
    assert "candidate" not in stamped
    assert "graph" not in stamped
    assert "accepted_batch" not in stamped


def test_pure_clarify_survives_authority_stamping_without_replay_mismatch(
    tmp_path: Path,
) -> None:
    """R1 leg 4 regression: a terminal pure clarification (question only — no
    operations, no accepted batch, no candidate graph, graph unchanged) must
    keep its question, ``outcome.kind="clarify"`` and ``no_candidate_reason``
    instead of being overwritten as ``authority_replay_mismatch``.
    """
    class_type = "Rodin3D_Regular"
    provider = _Provider(
        {
            class_type: NodeSchema(
                class_type=class_type,
                pack="test",
                inputs={"widget_0": InputSpec(type="CHOICE", required=True)},
                outputs=[],
            )
        }
    )
    submit_graph = _single_widget_graph(class_type)
    question = (
        "Which Rodin variant should stay enabled: Regular, Detail, Smooth, "
        "or Sketch?"
    )
    response = {
        "message": question,
        "graph_unchanged": True,
        "no_candidate_reason": "clarification_requested",
        "outcome": {
            "kind": "clarify",
            "question": question,
            "graph_unchanged": True,
        },
        "apply_eligible": False,
        "canvas_apply_allowed": False,
        "queue_allowed": False,
    }
    assert _response_claims_applyable(response) is False

    receipt, stamped = build_and_persist_authority_receipt(
        turn_dir=tmp_path / "turns" / "0001",
        session_id="pure-clarify",
        turn_id="0001",
        request_payload={"graph": submit_graph},
        response=response,
        schema_version="2.0.0",
        schema_provider=provider,
    )

    assert receipt.is_applyable is False
    # The clarification envelope survives verbatim; nothing is rewritten.
    assert stamped["message"] == question
    assert stamped["outcome"]["kind"] == "clarify"
    assert stamped["outcome"]["question"] == question
    assert stamped["no_candidate_reason"] == "clarification_requested"
    assert stamped["no_candidate_reason"] != "authority_replay_mismatch"
    assert stamped["graph_unchanged"] is True
    assert stamped.get("accepted_batch") is None
    assert "candidate" not in stamped
    # Receipt reference is still stamped so the turn stays auditable.
    assert isinstance(stamped.get("authority_receipt"), dict)


def test_pure_clarify_with_apply_claim_fails_closed(tmp_path: Path) -> None:
    """R1BR-002 regression: a clarify-labeled response carrying ANY
    applyability claim (every spelling of the canonical detector) is NOT a
    pure clarification — preservation is refused and the false authority
    fails closed as a generic authority rejection."""
    class_type = "Rodin3D_Regular"
    provider = _Provider(
        {
            class_type: NodeSchema(
                class_type=class_type,
                pack="test",
                inputs={"widget_0": InputSpec(type="CHOICE", required=True)},
                outputs=[],
            )
        }
    )
    submit_graph = _single_widget_graph(class_type)
    question = "Which Rodin variant should stay enabled?"
    base_response = {
        "message": question,
        "graph_unchanged": True,
        "no_candidate_reason": "clarification_requested",
        "outcome": {
            "kind": "clarify",
            "question": question,
            "graph_unchanged": True,
        },
    }
    spoofs = (
        {"apply_eligible": True},
        {"canvas_apply_allowed": True},
        {"apply_allowed": True},
        {"queue_allowed": True},
        {"eligibility": {"applyable": True}},
        {"apply_eligibility": {"applyable": True}},
    )
    for index, spoof in enumerate(spoofs):
        response = dict(base_response)
        response.update(spoof)
        assert _response_claims_applyable(response) is True

        receipt, stamped = build_and_persist_authority_receipt(
            turn_dir=tmp_path / "turns" / f"{index:04d}",
            session_id="pure-clarify-apply-spoof",
            turn_id=f"{index:04d}",
            request_payload={"graph": submit_graph},
            response=response,
            schema_version="2.0.0",
            schema_provider=provider,
        )

        assert receipt.is_applyable is False
        # Not preserved: generic rejection strips every authority claim.
        assert stamped["no_candidate_reason"] == "authority_replay_mismatch"
        assert stamped["message"] != question
        for field in (
            "apply_eligible",
            "apply_allowed",
            "canvas_apply_allowed",
            "queue_allowed",
        ):
            assert stamped[field] is False
        for eligibility_field in ("eligibility", "apply_eligibility"):
            assert stamped[eligibility_field]["applyable"] is False
        assert stamped["outcome"]["kind"] == "error"


def test_pure_clarify_with_candidate_transaction_fails_closed(
    tmp_path: Path,
) -> None:
    """R1BR-002 regression: candidate authority WITHOUT a ``candidate.graph``
    (a top-level ``candidate_transaction`` aggregate, or a bare
    ``candidate``/``candidate_graph`` payload) also vetoes the pure-clarify
    preservation path — such a response must fail closed."""
    class_type = "Rodin3D_Regular"
    provider = _Provider(
        {
            class_type: NodeSchema(
                class_type=class_type,
                pack="test",
                inputs={"widget_0": InputSpec(type="CHOICE", required=True)},
                outputs=[],
            )
        }
    )
    submit_graph = _single_widget_graph(class_type)
    question = "Which Rodin variant should stay enabled?"
    base_response = {
        "message": question,
        "graph_unchanged": True,
        "no_candidate_reason": "clarification_requested",
        "outcome": {
            "kind": "clarify",
            "question": question,
            "graph_unchanged": True,
        },
    }
    candidate_authority_payloads = (
        {
            "candidate_transaction": {
                "contract_version": "candidate_transaction_v2",
                "state": "candidate",
            },
        },
        {"candidate": {"state": "candidate_ready"}},
        {"candidate_graph": {"last_node_id": 1}},
    )
    for index, payload in enumerate(candidate_authority_payloads):
        response = dict(base_response)
        response.update(payload)
        assert _response_claims_applyable(response) is False

        receipt, stamped = build_and_persist_authority_receipt(
            turn_dir=tmp_path / "turns" / f"{index:04d}",
            session_id="pure-clarify-candidate-spoof",
            turn_id=f"{index:04d}",
            request_payload={"graph": submit_graph},
            response=response,
            schema_version="2.0.0",
            schema_provider=provider,
        )

        assert receipt.is_applyable is False
        assert stamped["no_candidate_reason"] == "authority_replay_mismatch"
        assert stamped["message"] != question
        assert "candidate" not in stamped
        assert "graph" not in stamped
        assert "candidate_graph" not in stamped
        assert "candidate_transaction" not in stamped
        assert stamped["outcome"]["kind"] == "error"


def test_edit_with_clarify_and_operations_still_fails_closed(
    tmp_path: Path,
) -> None:
    """An edit response whose outcome says clarify but which carries accepted
    operations and a candidate graph is NOT a pure clarification: it must
    still be rejected as authority_replay_mismatch."""
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
    # Tamper the product so replay cannot match: the response claims clarify
    # but ships a candidate graph its own accepted delta never produced.
    candidate = _single_widget_graph(class_type)
    candidate["nodes"][0]["widgets_values"] = ["not the accepted value"]
    op = {
        "op": "set_node_field",
        "target": ["", "133", "prompt"],
        "value": "maybe this?",
    }
    response = {
        "message": "I tentatively changed the prompt — clarify first?",
        "graph": candidate,
        "candidate": {"state": "candidate_ready", "graph": candidate},
        "accepted_batch": [{"statement_index": 1, "op": op}],
        "agent_edit_protocol": "v2_delta",
        "apply_eligibility": {"applyable": True, "reason": "applyable"},
        "graph_unchanged": False,
        "outcome": {"kind": "clarify", "question": "Did you mean this?"},
    }

    receipt, stamped = build_and_persist_authority_receipt(
        turn_dir=tmp_path / "turns" / "0001",
        session_id="edit-with-clarify",
        turn_id="0001",
        request_payload={"graph": submit_graph},
        response=response,
        schema_version="2.0.0",
        schema_provider=provider,
    )

    assert receipt.is_applyable is False
    assert stamped["no_candidate_reason"] == "authority_replay_mismatch"
    assert stamped["apply_eligible"] is False
