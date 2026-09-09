from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest


_R5_FIXTURES = Path(__file__).parent / "fixtures" / "workflow_execution_spine_r5"

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    _response_claims_applyable,
    build_and_persist_authority_receipt,
    build_authority_receipt,
    verify_replay,
)
from vibecomfy.porting.edit.ops import canonical_op_to_dict
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.schema import (
    InputSpec,
    NodeSchema,
    OutputSpec,
    capture_schema_snapshot,
    schema_payload_from_node_schema,
)
from vibecomfy.testing.canonical import canonical_bytes, canonical_digest, canonical_json
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class _Provider:
    def __init__(
        self,
        schemas: dict[str, NodeSchema],
        *,
        node_classes: dict[str, str] | None = None,
        missing_classes: tuple[str, ...] = (),
    ) -> None:
        self._schemas = schemas
        payloads = {
            class_type: schema_payload_from_node_schema(class_type, schema)
            for class_type, schema in schemas.items()
        }
        self.snapshot = capture_schema_snapshot(
            class_types=sorted({*payloads, *missing_classes}),
            request_snapshot={
                "contract_version": "schema_snapshot_v1",
                "schemas": payloads,
                "missing_classes": list(missing_classes),
            },
            node_classes=node_classes,
        )

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def test_shared_canonical_hash_leaf_is_order_independent_and_exact() -> None:
    left = {"z": [2, 1], "a": {"β": "é", "n": 1}}
    right = {"a": {"n": 1, "β": "é"}, "z": [2, 1]}
    assert canonical_json(left) == '{"a":{"n":1,"β":"é"},"z":[2,1]}'
    assert canonical_bytes(left) == canonical_json(right).encode("utf-8")
    assert canonical_digest(left) == canonical_digest(right)


def test_semantic_projection_derives_edge_identity_and_excludes_ui_metadata() -> None:
    workflow = VibeWorkflow("canonical", WorkflowSource("canonical"))
    workflow.nodes["source"] = VibeNode(
        "source", "Source", uid="src", metadata={"semantic": {"role": "input"}, "presentation": {"x": 1}}
    )
    workflow.nodes["sink"] = VibeNode("sink", "Sink", uid="dst")
    workflow.connect("source.0", "sink.image")
    projection = workflow.semantic_projection()
    assert projection["edges"] == [{
        "scope_path": "", "from_uid": "src", "from_port": "0", "to_uid": "dst", "to_port": "image"
    }]
    source_projection = next(node for node in projection["nodes"] if node["uid"] == "src")
    assert source_projection["metadata"] == {"role": "input"}
    assert "presentation" not in repr(projection)


def test_variant_selection_changes_execution_without_changing_semantic_definition() -> None:
    workflow = VibeWorkflow("variants", WorkflowSource("variants"))
    workflow.nodes["1"] = VibeNode("1", "Prompt", uid="prompt", inputs={"text": "base"})
    workflow.variants = {"bright": {"prompt.text": "bright"}}
    before = workflow.semantic_digest()
    assert workflow.compile(variant="bright")["1"]["inputs"]["text"] == "bright"
    assert workflow.semantic_digest() == before


def test_identity_validation_rejects_blank_duplicate_and_qualified_uids() -> None:
    workflow = VibeWorkflow("identity", WorkflowSource("identity"))
    workflow.nodes["1"] = VibeNode("1", "A", uid="")
    workflow.nodes["2"] = VibeNode("2", "B", uid="same")
    workflow.nodes["3"] = VibeNode("3", "C", uid="same")
    issues = workflow.identity_issues()
    assert {issue.code for issue in issues} == {"invalid_node_uid", "duplicate_node_uid"}
    workflow.nodes["1"].uid = "scope#qualified"
    with pytest.raises(ValueError, match="qualified"):
        workflow.semantic_projection()


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
        },
        node_classes={"133": class_type, "200": "UntouchedUnknownNode"},
        missing_classes=("UntouchedUnknownNode",),
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
        },
        node_classes={"1": class_type},
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
        schema_provider=_Provider(
            {},
            node_classes={"34": "LayerMask: SegmentAnythingUltra V3", "99": "UntouchedUnknownNode"},
            missing_classes=("LayerMask: SegmentAnythingUltra V3", "UntouchedUnknownNode"),
        ),
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
        },
        node_classes={"1": "KnownPromptNode"},
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


def test_positional_widget_seals_via_explicit_frozen_schema() -> None:
    """The retained schema resolves widget_0 to one named canonical field."""
    session = EditSession(
        _single_widget_graph("IndexTTSEmotionOptionsNode", uid="125"),
        schema_provider=_Provider(
            {
                "IndexTTSEmotionOptionsNode": NodeSchema(
                    class_type="IndexTTSEmotionOptionsNode",
                    pack="ComfyUI-IndexTTS",
                    inputs={
                        "emotion_control": InputSpec(
                            type="STRING", required=False, default="neutral"
                        )
                    },
                    outputs=[],
                )
            },
            node_classes={"125": "IndexTTSEmotionOptionsNode"},
        ),
    )

    result = session.apply_batch(
        "indexttsemotionoptionsnode.widget_0 = 'cannot be named honestly'"
    )

    assert result.ok is True
    assert len(result.landed_ops) == 1
    assert result.landed_ops[0].target.field_path == "emotion_control"
    # The explicit frozen schema makes both the old and new values
    # resolvable; no stale ambient-cache diagnostic is manufactured.
    assert result.statements[0].diagnostics == ()


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
        schema_provider=_Provider(
            {},
            node_classes={"34": class_type},
            missing_classes=(class_type,),
        ),
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
        schema_provider=_Provider(
            {},
            node_classes={"138": class_type},
            missing_classes=(class_type,),
        ),
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
        },
        node_classes={"133": "KnownPromptNode"},
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
        },
        node_classes={"133": class_type},
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
        },
        node_classes={"133": class_type},
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
        },
        node_classes={"133": class_type},
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
