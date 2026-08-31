"""Model-selected typed refusal actions fail closed at the authority seam."""

from __future__ import annotations

from types import SimpleNamespace

from vibecomfy.comfy_nodes.agent._frag_batch_reports import split_terminal_clarify
from vibecomfy.comfy_nodes.agent._frag_response_contract import (
    _record_named_schema_absence_blocker,
    _typed_refusal_is_authorized,
)
from vibecomfy.executor.prompts import parse_reply_payload
from vibecomfy.executor.contracts import ExecutorRequest
from vibecomfy.executor.threaded import synthesize_inspect_refusal_implementation


def _state(
    *,
    claimed: tuple[str, ...] = (),
    evidence: tuple[str, ...] = (),
    kind: str | None = "requires_custom_nodes",
    graph: object | None = None,
    statements: list[dict] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        task="Add MTCNN and RetinaFace face detection",
        request_payload={"query": "Add MTCNN and RetinaFace face detection"},
        graph=graph,
        batch_refusal_missing_classes=claimed,
        batch_refusal_evidence=evidence,
        batch_refusal_kind=kind,
        batch_turns=[
            {
                "statements": statements
                or [
                    {
                        "op_kind": "query",
                        "ok": True,
                        "landed": False,
                        "detail": {
                            "missing_classes": ["MTCNN", "RetinaFace"],
                        },
                    }
                ],
            }
        ],
        report={},
        user_message="The requested detector is unavailable.",
    )


def test_requires_custom_nodes_refusal_cites_exact_absence_ledger() -> None:
    action = split_terminal_clarify(
        'search(focus_types=["MTCNN", "RetinaFace"])\n'
        'refuse(kind="requires_custom_nodes", '
        'missing_classes=["MTCNN", "RetinaFace"], '
        'evidence=["schema:MTCNN", "schema:RetinaFace"], '
        'message="Install the detector pack to continue.")'
    )
    assert action.action == "refuse"
    assert action.kind == "requires_custom_nodes"
    assert action.missing_classes == ("MTCNN", "RetinaFace")
    state = _state(claimed=action.missing_classes, evidence=action.evidence)
    assert _record_named_schema_absence_blocker(state, has_candidate=False) == (
        "MTCNN",
        "RetinaFace",
    )
    assert _typed_refusal_is_authorized(
        state, named_schema_absence=True, structural_feature_absence=False
    )


def test_clarify_refusal_is_typed_and_keeps_exact_evidence() -> None:
    action = split_terminal_clarify(
        'refuse(kind="clarify", missing_classes=["MTCNN"], '
        'evidence=["schema:MTCNN"], '
        'message="Should I use another detector?")'
    )
    assert action.action == "refuse"
    assert action.kind == "clarify"
    assert action.missing_classes == ("MTCNN",)
    assert action.evidence == ("schema:MTCNN",)


def test_generic_done_has_no_typed_refusal_action() -> None:
    action = split_terminal_clarify('search(focus_types=["MTCNN"])\ndone()')
    assert action.action is None
    assert action.message is None
    state = _state(kind=None)
    _record_named_schema_absence_blocker(state, has_candidate=False)
    assert not _typed_refusal_is_authorized(
        state, named_schema_absence=True, structural_feature_absence=False
    )


def test_invented_or_partial_classes_fail_closed() -> None:
    for claimed in (("MTCNN",), ("MTCNN", "RetinaFace", "InventedDetector")):
        state = _state(claimed=claimed, evidence=("schema:MTCNN",))
        _record_named_schema_absence_blocker(state, has_candidate=False)
        assert not _typed_refusal_is_authorized(
            state, named_schema_absence=True, structural_feature_absence=False
        )


def test_failed_edit_cannot_be_laundered_into_refusal() -> None:
    state = _state(
        claimed=("MTCNN", "RetinaFace"),
        evidence=("schema:MTCNN", "schema:RetinaFace"),
        statements=[
            {
                "op_kind": "add_node",
                "ok": False,
                "landed": False,
                "detail": {"missing_classes": ["MTCNN", "RetinaFace"]},
            }
        ],
    )
    _record_named_schema_absence_blocker(state, has_candidate=False)
    assert not _typed_refusal_is_authorized(
        state, named_schema_absence=True, structural_feature_absence=False
    )


def test_present_class_cannot_be_claimed_absent() -> None:
    state = _state(
        claimed=("MTCNN", "RetinaFace"),
        evidence=("schema:MTCNN", "schema:RetinaFace"),
        graph={"nodes": {"1": {"class_type": "MTCNN"}}},
        statements=[
            {
                "op_kind": "query",
                "ok": True,
                "landed": False,
                "detail": {"missing_classes": ["MTCNN"]},
            }
        ],
    )
    assert _record_named_schema_absence_blocker(state, has_candidate=False) == ()


def test_reply_lane_preserves_typed_evidence_fields() -> None:
    payload = parse_reply_payload(
        '{"kind":"requires_custom_nodes",'
        '"missing_classes":["MTCNN"],'
        '"evidence":["schema:MTCNN"],'
        '"reply":"Install the detector pack."}'
    )
    assert payload.is_typed_refusal
    assert payload.missing_classes == ("MTCNN",)
    assert payload.evidence == ("schema:MTCNN",)


def test_threaded_lane_requires_model_typed_refusal_before_promotion() -> None:
    request = ExecutorRequest(
        query="Add MTCNN face detection",
        graph={"nodes": {}},
        expected_no_candidate_absent_classes=("MTCNN",),
    )
    def lookup(class_type: str) -> None:
        return None
    assert synthesize_inspect_refusal_implementation(
        request, reply="MTCNN is unavailable.", schema_lookup=lookup
    ) is None
    implementation = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"requires_custom_nodes",'
            '"missing_classes":["MTCNN"],'
            '"evidence":["schema:MTCNN"],'
            '"reply":"Install the detector pack."}'
        ),
        schema_lookup=lookup,
    )
    assert implementation is not None
    assert implementation.durable_response["outcome"]["kind"] == "requires_custom_nodes"
