"""Model-selected typed refusal actions fail closed at the authority seam."""

from __future__ import annotations

from types import SimpleNamespace
import re
from pathlib import Path

import pytest

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
from vibecomfy.executor.refusal_evidence import FrozenRefusalLedger
import vibecomfy.executor.refusal_evidence as refusal_evidence
import vibecomfy.executor.threaded as threaded_executor
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
    state.schema_provider = _route_test_provider()
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
        'refuse(kind="clarify", message="x", feature_absences=[{"evidence_id":"id","feature":"x"}], evidence=["id"])',
        'refuse(kind="clarify", message="x", evidence=["id", "id"])',
        'refuse(kind="requires_custom_nodes", message="x", missing_classes=["MTCNN", "MTCNN"], evidence=["id"])',
        'refuse(kind="clarify", message="x", evidence=[])',
        'refuse(kind="clarify", message="x", evidence=["id"])',
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


def test_partial_search_cannot_authorize_complete_named_refusal() -> None:
    state = _state(claimed=("MTCNN",), evidence=("schema:MTCNN",))
    state.schema_provider = _route_test_provider()
    state.batch_turns[0]["statements"][0]["detail"]["missing_classes"] = ["MTCNN"]
    assert _record_named_schema_absence_blocker(state, has_candidate=False) == ()
    assert "authoring_blocker" not in state.report
    state.batch_turns[0]["statements"].append(
        {
            "op_kind": "query",
            "ok": True,
            "landed": False,
            "detail": {"missing_classes": ["RetinaFace"]},
        }
    )
    _record_named_schema_absence_blocker(state, has_candidate=False)
    blocker = state.report["authoring_blocker"]
    assert blocker["missing_runtime_classes"] == ["MTCNN", "RetinaFace"]
    state.batch_refusal_missing_classes = ("MTCNN", "RetinaFace")
    state.batch_refusal_evidence = tuple(
        item["evidence_id"] for item in blocker["absence_evidence"]
    )
    assert _typed_refusal_is_authorized(
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
    state.schema_provider = _route_test_provider()
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


def test_threaded_typed_classes_reject_lossy_non_string_items() -> None:
    with pytest.raises(ValueError):
        parse_reply_payload(
            '{"kind":"requires_custom_nodes","missing_classes":["MTCNN",7],'
            '"evidence":["id"],"reply":"MTCNN is absent."}'
        )
    for raw in (
        '{"kind":"clarify","evidence":["id"],"reply":"x","extra":1}',
        '{"kind":"clarify","feature_absences":[{"evidence_id":"id","feature":"x"}],"reply":"x"}',
        '{"kind":"clarify","evidence":[7],"reply":"x"}',
        '{"kind":"clarify","evidence":[],"missing_classes":["MTCNN"],"reply":"x"}',
        '{"kind":"clarify","evidence":["id"],"reply":"x"}',
        '{"kind":"requires_custom_nodes","missing_classes":["MTCNN"],"evidence":[],"reply":"x"}',
    ):
        with pytest.raises(ValueError):
            parse_reply_payload(raw)


def test_public_frozen_ledger_constructor_cannot_authenticate_fake_snapshot() -> None:
    with pytest.raises(TypeError, match="authority capture"):
        FrozenRefusalLedger.from_collection(
            {
                "refusal:v1:forged": {
                    "evidence_id": "refusal:v1:forged",
                    "kind": "class_absence",
                    "class_type": "MTCNN",
                    "authority_digest": "f" * 64,
                }
            },
            graph={"nodes": {"1": {"class_type": "MTCNN"}}},
            schema_snapshot={"MTCNN": None},
            schema_content_digest="fake",
        )


def test_direct_capture_helper_requires_owner_capability() -> None:
    assert not hasattr(refusal_evidence, "_issue_capture_owner")
    assert not hasattr(FrozenRefusalLedger, "_from_capture")
    with pytest.raises(TypeError, match="authority capture"):
        FrozenRefusalLedger({})


def test_direct_capture_rejects_forged_duck_owner() -> None:
    class DuckOwner:
        def _capture_capability(self) -> object:
            return object()

    assert hasattr(DuckOwner(), "_capture_capability")
    assert not hasattr(DuckOwner(), "_from_capture")


def test_direct_authority_construction_has_no_mint_seam() -> None:
    authority = threaded_executor._FrozenSchemaAuthority(lambda _class_type: None)
    assert not hasattr(authority, "_capture_capability")
    assert not hasattr(authority, "_from_capture")


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
    duplicate = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"requires_custom_nodes","kind":"clarify",'
            '"missing_classes":["MTCNN"],"evidence":["%s"],'
            '"reply":"MTCNN is unavailable."}'
        ) % evidence_id,
        schema_lookup=lookup,
        frozen_ledger=ledger,
    )
    assert duplicate is not None
    assert duplicate.durable_response["outcome"]["kind"] == "noop"
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


def test_threaded_structural_refusal_uses_frozen_feature_ledger() -> None:
    request = ExecutorRequest(
        query="Use the SaveImage missing_feature input",
        graph=_route_test_graph(),
        expected_no_candidate_absent_features=(
            {"feature": "missing_feature", "checks": [{
                "class_type": "saveimage", "member_kind": "input", "member": "missing_feature"
            }]},
        ),
    )
    provider = _route_test_provider()
    ledger = inspect_refusal_evidence_ledger(request, schema_lookup=provider)
    feature_id = next(
        key for key, record in ledger.items() if record["kind"] == "feature_absence"
    )
    implementation = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"clarify","feature_absences":[{"evidence_id":"%s"}],'
            '"evidence":["%s"],"reply":"Use another image sink."}'
        ) % (feature_id, feature_id),
        schema_lookup=provider,
        frozen_ledger=ledger,
    )
    assert implementation is not None
    assert implementation.durable_response["outcome"]["kind"] == "clarify"

    mutable = {"value": provider.get_schema("SaveImage")}
    def changing_lookup(class_type: str) -> object | None:
        value = mutable["value"]
        mutable["value"] = object()
        return value
    frozen = inspect_refusal_evidence_ledger(request, schema_lookup=changing_lookup)
    frozen_id = next(iter(frozen))
    stable = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"clarify","feature_absences":[{"evidence_id":"%s"}],'
            '"evidence":["%s"],"reply":"Use another image sink."}'
        ) % (frozen_id, frozen_id),
        schema_lookup=changing_lookup,
        frozen_ledger=frozen,
    )
    assert stable is not None
    assert stable.durable_response["outcome"]["kind"] == "clarify"


def test_threaded_frozen_class_ledger_is_not_recomputed() -> None:
    provider = _route_test_provider()
    calls = 0

    def lookup(class_type: str) -> object | None:
        nonlocal calls
        calls += 1
        # The first cached observation is the authority shown to the model;
        # later ambient state changes must not affect validation.
        return None if calls <= 2 else provider.get_schema("SaveImage")

    request = ExecutorRequest(
        query="Add MTCNN face detection",
        graph={"nodes": {}},
        expected_no_candidate_absent_classes=("MTCNN",),
    )
    frozen = inspect_refusal_evidence_ledger(request, schema_lookup=lookup)
    evidence_id = next(iter(frozen))
    result = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"requires_custom_nodes","missing_classes":["MTCNN"],'
            '"evidence":["%s"],"reply":"Install the detector pack."}'
        ) % evidence_id,
        schema_lookup=lookup,
        frozen_ledger=frozen,
    )
    assert result is not None
    assert result.durable_response["outcome"]["kind"] == "requires_custom_nodes"
    assert calls == 1


def test_threaded_forged_or_stale_frozen_ledger_fails_closed() -> None:
    request = ExecutorRequest(
        query="Add MTCNN face detection",
        graph={"nodes": {}},
        expected_no_candidate_absent_classes=("MTCNN",),
    )

    def lookup(_class_type: str) -> None:
        return None

    ledger = inspect_refusal_evidence_ledger(request, schema_lookup=lookup)
    evidence_id = next(iter(ledger))
    reply = (
        '{"kind":"requires_custom_nodes","missing_classes":["MTCNN"],'
        '"evidence":["%s"],"reply":"Install the detector pack."}'
    ) % evidence_id
    forged = dict(ledger)
    forged[evidence_id] = dict(ledger[evidence_id], authority_digest="f" * 64)
    forged_result = synthesize_inspect_refusal_implementation(
        request, reply=reply, schema_lookup=lookup, frozen_ledger=forged
    )
    assert forged_result is not None
    assert forged_result.durable_response["outcome"]["kind"] == "noop"

    request.graph["nodes"]["1"] = {"class_type": "MTCNN"}
    stale_result = synthesize_inspect_refusal_implementation(
        request, reply=reply, schema_lookup=lookup, frozen_ledger=ledger
    )
    assert stale_result is not None
    assert stale_result.durable_response["outcome"]["kind"] == "noop"


def test_threaded_provider_generation_change_invalidates_frozen_ledger() -> None:
    provider = _route_test_provider()
    request = ExecutorRequest(
        query="Add MTCNN face detection",
        graph={"nodes": {}},
        expected_no_candidate_absent_classes=("MTCNN",),
    )
    ledger = inspect_refusal_evidence_ledger(request, schema_lookup=provider)
    evidence_id = next(iter(ledger))
    provider._schemas["MTCNN"] = provider.get_schema("SaveImage")
    result = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"requires_custom_nodes","missing_classes":["MTCNN"],'
            '"evidence":["%s"],"reply":"Install the detector pack."}'
        ) % evidence_id,
        schema_lookup=provider,
        frozen_ledger=ledger,
    )
    assert result is not None
    assert result.durable_response["outcome"]["kind"] == "noop"


def test_threaded_markerless_provider_mutation_invalidates_frozen_ledger() -> None:
    class MarkerlessProvider:
        def __init__(self) -> None:
            self.schema: object | None = None

        def get_schema(self, _class_type: str) -> object | None:
            return self.schema

    provider = MarkerlessProvider()
    request = ExecutorRequest(
        query="Add MTCNN face detection",
        graph={"nodes": {}},
        expected_no_candidate_absent_classes=("MTCNN",),
    )
    ledger = inspect_refusal_evidence_ledger(request, schema_lookup=provider)
    evidence_id = next(iter(ledger))
    provider.schema = _route_test_provider().get_schema("SaveImage")
    result = synthesize_inspect_refusal_implementation(
        request,
        reply=(
            '{"kind":"requires_custom_nodes","missing_classes":["MTCNN"],'
            '"evidence":["%s"],"reply":"Install the detector pack."}'
        ) % evidence_id,
        schema_lookup=provider,
        frozen_ledger=ledger,
    )
    assert result is not None
    assert result.durable_response["outcome"]["kind"] == "noop"


def test_threaded_implicit_class_set_cannot_authorize_partial_search() -> None:
    request = ExecutorRequest(
        query="Add MTCNN and RetinaFace face detection",
        graph={"nodes": {}},
    )

    def lookup(_class_type: str) -> None:
        return None

    ledger = inspect_refusal_evidence_ledger(request, schema_lookup=lookup)
    assert {
        record["class_type"] for record in ledger.values()
        if record["kind"] == "class_absence"
    } == {"MTCNN", "RetinaFace"}


def test_staged_stale_authority_evidence_is_rejected() -> None:
    provider = _route_test_provider()
    state = _state(claimed=("MTCNN",))
    state.schema_provider = provider
    _record_named_schema_absence_blocker(state, has_candidate=False)
    evidence_id = state.report["authoring_blocker"]["evidence_refs"][0]
    original = provider.get_schema
    provider.get_schema = lambda _class_type: original("SaveImage")
    state.batch_refusal_evidence = (evidence_id,)
    assert not _typed_refusal_is_authorized(
        state, named_schema_absence=True, structural_feature_absence=False
    )

    state = _state(claimed=("MTCNN",))
    state.schema_provider = _route_test_provider()
    _record_named_schema_absence_blocker(state, has_candidate=False)
    state.graph = {"nodes": {"1": {"class_type": "MTCNN"}}}
    evidence_id = state.report["authoring_blocker"]["evidence_refs"][0]
    state.batch_refusal_evidence = (evidence_id,)
    assert not _typed_refusal_is_authorized(
        state, named_schema_absence=True, structural_feature_absence=False
    )


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
