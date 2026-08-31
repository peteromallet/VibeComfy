"""Model-selected typed refusal actions fail closed at the authority seam."""

from __future__ import annotations

from types import SimpleNamespace
import re
from pathlib import Path

from vibecomfy.comfy_nodes.agent._frag_batch_reports import split_terminal_clarify
from vibecomfy.comfy_nodes.agent._frag_response_contract import (
    _record_named_schema_absence_blocker,
    _record_structural_feature_absence_blocker,
    _typed_refusal_is_authorized,
)
from vibecomfy.executor.prompts import parse_reply_payload
from vibecomfy.executor.contracts import ExecutorRequest
from vibecomfy.executor.threaded import (
    inspect_refusal_evidence_ledger,
    synthesize_inspect_refusal_implementation,
)
from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
from tests.test_authority_nonapply_terminal import _route_test_graph, _route_test_provider
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


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
    state.batch_refusal_evidence = tuple(
        item["evidence_id"]
        for item in state.report["authoring_blocker"]["absence_evidence"]
    )
    assert _typed_refusal_is_authorized(state, named_schema_absence=True, structural_feature_absence=False)


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


def test_splitter_rejects_unknown_duplicate_and_nonterminal_refusal() -> None:
    cases = (
        'refuse(kind="clarify", message="x", extra="bad")',
        'refuse(kind="clarify", kind="requires_custom_nodes", message="x", evidence=["id"])',
        'refuse(kind="clarify", message="x", question="y", evidence=["id"])',
        'refuse(kind="clarify", message="x", evidence=["id"])\npython()',
    )
    for source in cases:
        result = split_terminal_clarify(source)
        assert result.action is None
        assert result.message is None


def test_direct_interpret_rejects_nonterminal_refusal() -> None:
    workflow = VibeWorkflow("refusal-grammar", WorkflowSource("refusal-grammar"))
    result = interpret(
        workflow,
        'refuse(kind="clarify", message="x", evidence=["id"])\npython()',
    )
    assert result.ok is False
    assert any(item.code == "refusal_must_be_terminal" for item in result.diagnostics)


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


def test_recomputed_wrong_authority_digest_is_rejected() -> None:
    state = _state(claimed=("MTCNN",))
    _record_named_schema_absence_blocker(state, has_candidate=False)
    original = dict(state.report["authoring_blocker"]["absence_evidence"][0])
    forged = dict(original, authority_digest="0" * 64)
    import hashlib
    forged["evidence_id"] = "refusal:v1:" + hashlib.sha256(
        f"class_absent|MTCNN|{forged['authority_digest']}".encode()
    ).hexdigest()[:24]
    state.report["authoring_blocker"]["absence_evidence"] = [forged]
    state.batch_refusal_evidence = (forged["evidence_id"],)
    assert not _typed_refusal_is_authorized(
        state, named_schema_absence=True, structural_feature_absence=False
    )


def test_structural_ledger_rejects_extra_and_duplicate_claims() -> None:
    state = _state(kind="clarify", graph=_route_test_graph())
    state.schema_provider = _route_test_provider()
    state.batch_turns = [{"statements": [{
        "op_kind": "query", "ok": True, "landed": False,
        "detail": {"feature_absences": [{"feature": "missing_feature", "checks": [{
            "class_type": "SaveImage", "member_kind": "input", "member": "missing_feature"
        }]}]},
    }]}]
    _record_structural_feature_absence_blocker(state, has_candidate=False)
    evidence_id = state.report["authoring_blocker"]["evidence_refs"][0]
    state.batch_refusal_feature_absences = ({"evidence_id": evidence_id},)
    state.batch_refusal_evidence = (evidence_id, evidence_id)
    assert not _typed_refusal_is_authorized(
        state, named_schema_absence=False, structural_feature_absence=True
    )
    state.batch_refusal_evidence = (evidence_id, "refusal:v1:invented")
    assert not _typed_refusal_is_authorized(
        state, named_schema_absence=False, structural_feature_absence=True
    )


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
    plain = synthesize_inspect_refusal_implementation(
        request, reply="MTCNN is unavailable.", schema_lookup=lookup
    )
    assert plain is not None
    assert plain.durable_response["outcome"]["kind"] == "noop"
    invalid = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"requires_custom_nodes",'
            '"missing_classes":["MTCNN"],'
            '"evidence":["bogus"],'
            '"reply":"MTCNN is unavailable."}'
        ),
        schema_lookup=lookup,
    )
    assert invalid is not None
    assert invalid.durable_response["outcome"]["kind"] == "noop"
    assert invalid.durable_response["report"]["authoring_blocker"]["refusal_validation"]["authorized"] is False
    malformed = synthesize_inspect_refusal_implementation(
        request, reply='{"kind":"requires_custom_nodes"', schema_lookup=lookup
    )
    assert malformed is not None
    assert malformed.durable_response["outcome"]["kind"] == "noop"
    assert "could not be authorized" in malformed.message.lower()
    ledger = inspect_refusal_evidence_ledger(request, schema_lookup=lookup)
    evidence_id = next(iter(ledger))
    implementation = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"requires_custom_nodes",'
            '"missing_classes":["MTCNN"],'
                f'"evidence":["{evidence_id}"],'
            '"reply":"Install the detector pack."}'
        ),
        schema_lookup=lookup,
    )
    assert implementation is not None
    assert implementation.durable_response["outcome"]["kind"] == "requires_custom_nodes"


def test_staged_structural_refusal_uses_produced_bound_evidence() -> None:
    calls: list[list[dict[str, str]]] = []

    def client(messages: list[dict[str, str]]) -> dict[str, str]:
        calls.append(messages)
        if len(calls) == 1:
            return {
                "batch": 'schema_check(class_type="SaveImage", member_kind="input", member="missing_feature")',
                "message": "Checking the exact SaveImage schema.",
            }
        ids = re.findall(r"refusal:v1:[a-f0-9]+", messages[-1]["content"])
        assert ids
        evidence_id = ids[-1]
        return {
            "batch": (
                'refuse(kind="clarify", '
                f'feature_absences=[{{"evidence_id":"{evidence_id}"}}], '
                f'evidence=["{evidence_id}"], '
                'message="Should I use another image sink?")'
            ),
            "message": "Should I use another image sink?",
        }

    result = handle_agent_edit(
        {
            "graph": _route_test_graph(),
            "workflow_id": "6b4611de-b2b2-42f2-b358-5f566d6a8933",
            "task": "Use the SaveImage missing_feature input",
            "session_id": "structural-refusal-e2e",
        },
        schema_provider=_route_test_provider(),
        deepseek_client=client,
        session_root=Path("/tmp"),
    )
    assert result["ok"] is True
    assert result["outcome"]["kind"] == "clarify"
    assert result["outcome"].get("feature_absences"), result


def test_staged_bogus_refusal_evidence_is_not_promoted() -> None:
    calls = 0

    def client(_messages: list[dict[str, str]]) -> dict[str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "batch": 'search(focus_types=["MTCNN"])',
                "message": "Checking the exact MTCNN schema.",
            }
        return {
            "batch": (
                'refuse(kind="requires_custom_nodes", missing_classes=["MTCNN"], '
                'evidence=["refusal:v1:bogus"], message="MTCNN is unavailable.")'
            ),
            "message": "MTCNN is unavailable.",
        }

    result = handle_agent_edit(
        {
            "graph": _route_test_graph(),
            "workflow_id": "6b4611de-b2b2-42f2-b358-5f566d6a8933",
            "task": "Add MTCNN face detection",
            "session_id": "bogus-refusal-e2e",
        },
        schema_provider=_route_test_provider(),
        deepseek_client=client,
        session_root=Path("/tmp"),
    )
    assert result["ok"] is True
    assert result["outcome"]["kind"] != "requires_custom_nodes"
    assert "typed_refusal_action" not in result.get("report", {})
