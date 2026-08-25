"""RR1-FIX(2) — honest non-apply terminals survive the authority boundary.

Finale evidence (batch-3 Hotshot/AnimateDiff, batch-4 face-detect, batch-5
Kolors/d813fe): zero-op, replay-clean turns carrying substantive answers or
typed class-absence proof were laundered into fabricated
``authority_replay_mismatch`` errors because the preserve-list recognized only
clarify-shaped terminals and the typed blocker required undocumented
clarification prose plus exact constructor-token matches.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    build_authority_receipt,
    stamp_response_with_authority,
)
from vibecomfy.comfy_nodes.agent.contracts import promote_requires_custom_nodes_outcome
from vibecomfy.comfy_nodes.agent._frag_response_contract import (
    _batch_named_schema_absences,
    _record_named_schema_absence_blocker,
)
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider
from vibecomfy.schema.types import (
    FrozenSchemaSnapshotProvider,
    capture_schema_snapshot,
    schema_payload_from_node_schema,
)

from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _route_test_provider() -> Any:
    class _Provider:
        def __init__(self, schemas: dict[str, NodeSchema]) -> None:
            self._schemas = schemas

        def get_schema(self, class_type: str) -> NodeSchema | None:
            return self._schemas.get(class_type)

        def schemas(self) -> dict[str, NodeSchema]:
            return self._schemas

    saveimage = NodeSchema(
        class_type="SaveImage",
        pack=None,
        inputs={
            "images": InputSpec("IMAGE", required=True),
            "filename_prefix": InputSpec("STRING"),
        },
        outputs=[],
        source_provider="test",
        confidence=1.0,
    )
    loadimage = NodeSchema(
        class_type="LoadImage",
        pack=None,
        inputs={"image": InputSpec("IMAGE")},
        outputs=[OutputSpec("IMAGE", "image")],
        source_provider="test",
        confidence=1.0,
    )
    return _Provider({"LoadImage": loadimage, "SaveImage": saveimage})

OBJECT_INFO_ROOT = "vibecomfy/porting/cache/object_info"


def _frozen_provider() -> FrozenSchemaSnapshotProvider:
    prov = ObjectInfoIndexSchemaProvider(OBJECT_INFO_ROOT)
    payload = schema_payload_from_node_schema(
        "TripoTextureNode", prov.get_schema("TripoTextureNode")
    )
    snap = capture_schema_snapshot(
        class_types=["TripoTextureNode"],
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": {"TripoTextureNode": payload},
            "missing_classes": [],
        },
        node_classes={"26": "TripoTextureNode"},
    )
    return FrozenSchemaSnapshotProvider(snap)


def _submit_graph() -> dict:
    return json.loads(
        r'''
{"nodes":[
  {"id":26,"type":"TripoTextureNode","mode":0,"pos":[0,0],"size":[270,174],"flags":{},"order":0,"properties":{},
   "inputs":[{"name":"model_task_id","type":"MODEL_TASK_ID","link":null}],
   "outputs":[{"name":"model_file","type":"STRING","links":null}],
   "widgets_values":[true,true,42,"standard","original_image"]}
 ],
 "links":[]}
'''
    )


def _noop_receipt_response() -> tuple[dict, dict]:
    frozen = _frozen_provider()
    submit = _submit_graph()
    receipt = build_authority_receipt(
        session_id="s",
        turn_id="t",
        submit_graph=submit,
        # No cumulative delta at all: empty accepted batch, null candidate,
        # replay-clean identity (op_count 0, replay_ok true).
        cumulative_delta_envelope=None,
        candidate=None,
        response={},
        schema_provider=frozen,
    )
    assert receipt.replay.replay_ok is True
    assert receipt.replay.op_count == 0
    assert receipt.candidate_hash is None
    response = {
        "message": (
            "Both approaches are tensorially identical here; denoise ≈ 0.8 "
            "keeps temporal coherence anchored to the input image."
        ),
        "reply": "same substantive answer",
        "graph_unchanged": True,
        "accepted_batch": [],
        "outcome": {"kind": "noop"},
        "no_candidate_reason": "no_changes",
    }
    return dict(response), receipt


def test_honest_noop_terminal_preserved_verbatim() -> None:
    """Zero-op replay-clean terminals keep outcome and substantive message."""
    response, receipt = _noop_receipt_response()
    stamped = stamp_response_with_authority(copy.deepcopy(response), receipt)
    assert stamped["authority_receipt"]["replay_ok"] is True
    assert stamped["authority_receipt"]["op_count"] == 0
    assert stamped["outcome"]["kind"] == "noop"
    assert stamped["message"] == response["message"]
    assert stamped.get("no_candidate_reason") != "authority_replay_mismatch"
    assert "Server replay verification failed" not in str(stamped.get("message"))


def test_candidate_authority_still_fails_closed() -> None:
    """A candidate payload under the same shape is NOT preserved."""
    from vibecomfy.schema.types import schema_payload_from_node_schema as _sp

    frozen = _frozen_provider()
    submit = _submit_graph()
    receipt = build_authority_receipt(
        session_id="s",
        turn_id="t",
        submit_graph=submit,
        cumulative_delta_envelope=None,
        candidate={"graph": {"nodes": {"26": {"class_type": "TripoTextureNode"}}}},
        response={},
        schema_provider=frozen,
    )
    response = {
        "message": "attempted",
        "graph_unchanged": True,
        "accepted_batch": [],
        "candidate": {"graph": {"nodes": {"26": {"class_type": "TripoTextureNode"}}}},
        "outcome": {"kind": "noop"},
    }
    stamped = stamp_response_with_authority(dict(response), receipt)
    assert stamped.get("no_candidate_reason") == "authority_replay_mismatch"
    assert stamped.get("apply_eligible") is False


def _absence_state(query: str, missing: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        task="edit_graph",
        request_payload={"query": query},
        batch_turns=[
            {
                "statements": [
                    {"detail": {"missing_classes": list(missing)}},
                ]
            }
        ],
        user_message="No authorable class is available in this runtime.",
        report={},
    )


def test_family_token_matches_request_named_absences() -> None:
    """A family term in the request names longer missed classes."""
    state = _absence_state(
        "Swap the detector to GroundingDINO",
        ["GroundingDinoModelLoader", "GroundingDinoSAMSegment"],
    )
    assert _batch_named_schema_absences(state) == (
        "GroundingDinoModelLoader",
        "GroundingDinoSAMSegment",
    )


def test_unrelated_miss_never_counts_as_named() -> None:
    state = _absence_state(
        "Swap the detector to GroundingDINO",
        ["TotallyUnrelatedPack"],
    )
    assert _batch_named_schema_absences(state) == ()


def test_blocker_records_from_typed_evidence_without_prose() -> None:
    """Plain-prose stops still attach the typed absence blocker."""
    state = _absence_state(
        "Add MTCNN face detection",
        ["MTCNN", "RetinaFace"],
    )
    missing = _record_named_schema_absence_blocker(state, has_candidate=False)
    assert missing == ("MTCNN", "RetinaFace")
    blocker = state.report["authoring_blocker"]
    assert blocker["reason"] == "named_class_absent_from_schema"
    assert blocker["missing_runtime_classes"] == ["MTCNN", "RetinaFace"]


def test_blocker_skipped_when_candidate_exists() -> None:
    state = _absence_state("Add MTCNN face detection", ["MTCNN"])
    assert _record_named_schema_absence_blocker(state, has_candidate=True) == ()
    assert "authoring_blocker" not in state.report


def test_promotion_projects_error_envelope_under_typed_evidence() -> None:
    promoted = promote_requires_custom_nodes_outcome(
        {"kind": "error", "message": "gate refused"},
        missing_classes=["MTCNN"],
    )
    assert promoted["kind"] == "requires_custom_nodes"
    assert promoted["missing_classes"] == ["MTCNN"]

    untouched = promote_requires_custom_nodes_outcome(
        {"kind": "error", "message": "gate refused"},
        missing_classes=[],
    )
    assert untouched["kind"] == "error"


def _route_test_graph() -> dict:
    workflow_id = "6b4611de-b2b2-42f2-b358-5f566d6a8933"
    wf = VibeWorkflow(workflow_id, WorkflowSource(workflow_id))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "2.images")
    graph = emit_ui_json(wf, schema_provider=_route_test_provider())
    for node in graph["nodes"]:
        node.setdefault("properties", {})["vibecomfy_uid"] = str(node["id"])
    return graph


def test_route_agrees_with_promoted_requires_custom_nodes(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """A promoted typed terminal forces response.route into agreement.

    Batch-5 d813fe evidence: the refusal carried an edit route, contradicting
    the non-edit-route contract check.  The typed absence here is produced by
    the real chain — in-batch ``search(focus_types=["MTCNN"])`` records a
    provider-backed miss in statement detail, the recorder persists it, and
    promotion rewrites the terminal — so the route stamp must follow.
    """
    from unittest.mock import patch as _patch

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")

    def client(_messages):
        return {
            "batch": 'search(focus_types=["MTCNN"])\ndone()',
            "message": "Checking whether MTCNN exists in this runtime.",
        }

    with _patch(
        "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
        lambda **_kwargs: {"json": {}},
    ):
        result = handle_agent_edit(
            {
                "graph": _route_test_graph(),
                "workflow_id": "6b4611de-b2b2-42f2-b358-5f566d6a8933",
                "task": "Add MTCNN face detection before saving the image",
                "session_id": "mtcnn-absence-route-agreement",
            },
            schema_provider=_route_test_provider(),
            deepseek_client=client,
            session_root=tmp_path,
        )
    assert result["ok"] is True
    assert result["outcome"]["kind"] == "requires_custom_nodes"
    assert result["route"] == "requires_custom_nodes"


def test_persisted_finale_hotshot_receipt_preserves_honest_terminal() -> None:
    """Regression against the PERSISTED finale receipt, not a synthetic shape.

    Source: /tmp/t7-finale3/threaded/finale3/hotshot-16-frames-agent-edit —
    out/editor_sessions/8d1e30ef2ed44aeb8d4cefc701403548/turns/0001/authority/
    receipt.json.  The turn replayed clean (replay_ok=true, op_count=0) with a
    null candidate on BOTH sides, yet error="candidate_hash_mismatch" and
    candidate_matches=false were persisted — the artifact of comparing the
    null candidate against the recomputed empty apply.  The old gate read that
    artifact as a replay failure and laundered the terminal into
    authority_replay_mismatch (response.json: apply_eligibility.reason
    "authority_rejected").
    """
    from vibecomfy.comfy_nodes.agent.authority_receipts import AuthorityReceipt

    receipt = AuthorityReceipt.from_dict(
        {
            "schema_version": "2.0.0",
            "session_id": "8d1e30ef2ed44aeb8d4cefc701403548",
            "turn_id": "0001",
            "submit_graph_hash": (
                "bebc16f6e8399628cf3bb30695bda7c55fb4ffb285210e92265f07de3f3ca6a7"
            ),
            "submit_graph_bytes_sha256": (
                "bebc16f6e8399628cf3bb30695bda7c55fb4ffb285210e92265f07de3f3ca6a7"
            ),
            "accepted_batch_digest": (
                "bd168d1726936d61ae40a8528295c61d5efa256ed07fa96abb8768d2a77ea412"
            ),
            "cumulative_delta_hash": (
                "bd168d1726936d61ae40a8528295c61d5efa256ed07fa96abb8768d2a77ea412"
            ),
            "candidate_hash": None,
            "replay": {
                "replay_ok": True,
                "candidate_matches": False,
                "error": "candidate_hash_mismatch",
                "op_count": 0,
                "verification_kind": "delta_replay",
                "persisted_candidate_hash": None,
                "recomputed_candidate_hash": (
                    "2866d613db9b5afca1b4346038a64c990284e8bd605d88b9194b5159fc23425a"
                ),
            },
            "response_metadata": {
                "response_hash": (
                    "09a9d31e24c951b51f51c1a22e4742c36797f9d0a8b7f8f97b18f959ebc09dbc"
                ),
                "eligibility_hash": (
                    "52374891d3c653578e3c49e181626233cc1d637133bfde87ac06406c0e68d09c"
                ),
                "outcome_hash": (
                    "346da903af7ca594830ac77d35e27a1d5ae98a30bc5bee220e3bd53891c33737"
                ),
            },
            "created_at": "2026-08-24T23:43:36Z",
        }
    )
    response = {
        "message": (
            "AnimateDiff needs the Hotshot pack, which this runtime does not "
            "provide; the base sampler path stays unchanged."
        ),
        "graph_unchanged": True,
        "accepted_batch": [],
        "outcome": {"kind": "noop"},
        "no_candidate_reason": "no_changes",
    }
    stamped = stamp_response_with_authority(dict(response), receipt)
    assert stamped["outcome"]["kind"] == "noop"
    assert stamped["message"] == response["message"]
    assert stamped.get("no_candidate_reason") != "authority_replay_mismatch"
    assert stamped["authority_receipt"]["candidate_matches"] is False
