"""T20 retained schema/workflow witness binding regressions."""

from __future__ import annotations

import json
import copy
from dataclasses import replace
import inspect
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    capture_ingress_schema_snapshot,
)
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.ingest.snapshot import bind_snapshot_lineage, snapshot_of
from vibecomfy.porting.edit.admit import (
    AdmissionAllowed,
    AdmissionSnapshot,
    admit_operations,
    admission_snapshot_for,
    snapshot_from_schema_witness,
)
from vibecomfy.porting.edit.lint import LintIndex, lint_delta
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOpParseError,
    LinkSourceRef,
    NodeTarget,
    SetModeOp,
    canonical_op_to_dict,
    parse_edit_op,
)
from vibecomfy.porting.edit._session_types import _freeze_operation_tuple
from vibecomfy.porting.edit.checkpoint import accepted_delta_id
from vibecomfy.schema import SchemaSnapshotError
from vibecomfy.schema.types import (
    SchemaSnapshot,
    SchemaSnapshotIdentity,
    _digest_body,
    _schema_snapshot_digest,
    schema_snapshot_to_payload,
)


def _fixture() -> dict:
    return json.loads(
        Path("tests/fixtures/agent_edit/flat.json").read_text(encoding="utf-8")
    )


def _authority() -> tuple[dict, object, object, AdmissionSnapshot, LintIndex]:
    from tests.test_porting_edit_lint import _DeclaredProvider

    graph = _fixture()
    provider = _DeclaredProvider()
    workflow = from_ui(dict(graph), schema_provider=provider, use_comfy_converter=False)
    schema = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)
    retained = AdmissionSnapshot(workflow=snapshot_of(workflow), schema=schema)
    return graph, provider, workflow, retained, LintIndex.build(graph)


class _PoisonProvider:
    def __init__(self) -> None:
        self.calls = 0

    def get_schema(self, _class_type: str):
        self.calls += 1
        raise AssertionError("explicit retained authority must not query live provider")


def _op() -> SetModeOp:
    return SetModeOp(op="set_mode", target=NodeTarget(scope_path="", uid="1"), mode=2)


def test_explicit_retained_pair_succeeds_without_or_querying_provider() -> None:
    graph, _provider, workflow, retained, index = _authority()
    poison = _PoisonProvider()
    result = lint_delta(
        [_op()],
        index,
        schema_provider=poison,
        retained_authority=retained,
        pre_workflow=workflow,
        pre_ui_payload=graph,
        schema_snapshot=retained.schema,
    )
    assert result.rejected_count == 0
    assert poison.calls == 0


def test_digest_valid_changed_schema_cannot_use_provider_wrapper_shortcut() -> None:
    graph, provider, workflow, retained, index = _authority()
    changed = replace(retained.schema, generation=retained.schema.generation + 1, content_digest="")
    changed = replace(changed, content_digest=_schema_snapshot_digest(_digest_body(changed)))
    with pytest.raises(SchemaSnapshotError, match="retained"):
        lint_delta(
            [_op()],
            index,
            schema_provider=type("Wrapper", (), {"snapshot": changed})(),
            retained_authority=retained,
            pre_workflow=workflow,
            pre_ui_payload=graph,
            schema_snapshot=changed,
        )


def test_lint_delta_requires_retained_authority_even_with_frozen_wrapper() -> None:
    graph, provider, workflow, retained, index = _authority()
    with pytest.raises(TypeError, match="retained_authority"):
        lint_delta(
            [_op()],
            index,
            schema_provider=provider,
            pre_workflow=workflow,
            pre_ui_payload=graph,
            schema_snapshot=retained.schema,
        )


def test_direct_preview_rejects_cross_lineage_workflow_before_empty_or_nonempty_eval() -> None:
    graph, provider, workflow, retained, index = _authority()
    forged_workflow = workflow.copy()
    bind_snapshot_lineage(forged_workflow, session_id="different-session")
    with pytest.raises(SchemaSnapshotError, match="lineage"):
        lint_delta(
            [],
            index,
            schema_provider=provider,
            retained_authority=retained,
            pre_workflow=forged_workflow,
            pre_ui_payload=graph,
            schema_snapshot=retained.schema,
        )


def test_empty_delta_still_rejects_schema_disagreement() -> None:
    graph, provider, workflow, retained, index = _authority()
    forged = replace(retained.schema, generation=retained.schema.generation + 1, content_digest="")
    forged = replace(forged, content_digest=_schema_snapshot_digest(_digest_body(forged)))
    with pytest.raises(SchemaSnapshotError, match="retained"):
        lint_delta(
            [],
            index,
            schema_provider=provider,
            retained_authority=retained,
            pre_workflow=workflow,
            pre_ui_payload=graph,
            schema_snapshot=forged,
        )


def test_public_authority_arguments_are_exactly_typed_and_required() -> None:
    from vibecomfy.porting.edit.session import preview_lint_delta

    assert inspect.signature(lint_delta).parameters["retained_authority"].annotation == "AdmissionSnapshot"
    assert inspect.signature(preview_lint_delta).parameters["retained_authority"].annotation == "AdmissionSnapshot"


def _digest_valid_payload_with_mutation(schema: object, mutate) -> dict:
    payload = copy.deepcopy(schema_snapshot_to_payload(schema))
    mutate(payload)
    # Reproduce only the parser's *normalized digest body* so this remains a
    # digest-valid adversarial witness.  Admission must reject the original
    # malformed shape before those parser filters/coercions become authority.
    identity = payload["identity"]
    schemas_raw = payload["schemas"]
    normalized = SchemaSnapshot(
        identity=SchemaSnapshotIdentity(
            runtime_fingerprint=identity.get("runtime_fingerprint"),
            cache_fingerprint=identity.get("cache_fingerprint"),
            request_fingerprint=identity.get("request_fingerprint"),
            server_url=identity.get("server_url"),
        ),
        content_digest="",
        precedence=tuple(item for item in payload.get("precedence", ()) if isinstance(item, str)),
        selected_source=str(payload.get("selected_source") or ""),
        generation=int(payload.get("generation") or 0),
        conflicts=tuple(item for item in payload.get("conflicts", ()) if isinstance(item, str)),
        timestamp=payload.get("timestamp") if isinstance(payload.get("timestamp"), str) else None,
        version=str(payload.get("version") or "schema-snapshot-v1"),
        schemas={str(class_type): dict(raw) for class_type, raw in schemas_raw.items() if isinstance(raw, dict)},
        missing_classes=tuple(item for item in payload.get("missing_classes", ()) if isinstance(item, str)),
        input_order={
            str(class_type): tuple(str(name) for name in names if isinstance(name, str))
            for class_type, names in payload.get("input_order", {}).items()
            if isinstance(names, list)
        },
        node_classes={
            str(uid): str(class_type)
            for uid, class_type in payload.get("node_classes", {}).items()
            if str(uid) and isinstance(class_type, str) and class_type
        },
        workflow_observation_authoritative=False,
        ambient_lookup_forbidden=True,
    )
    payload["content_digest"] = _schema_snapshot_digest(_digest_body(normalized))
    return payload


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["input_order"].update({"A": "ab"}),
        lambda payload: payload["missing_classes"].append(7),
        lambda payload: payload["node_classes"].update({"1": 9}),
        lambda payload: payload["schemas"]["A"]["inputs"] .update({"bad": 9}),
        lambda payload: payload["schemas"]["A"]["outputs"].append({"type": 9, "name": None}),
    ],
    ids=["input-order", "missing-class", "node-class", "nested-input", "nested-output"],
)
def test_digest_valid_malformed_nested_payload_fails_before_admission(mutate) -> None:
    graph, provider, workflow, retained, index = _authority()
    payload = _digest_valid_payload_with_mutation(retained.schema, mutate)
    with pytest.raises(SchemaSnapshotError, match="malformed"):
        lint_delta(
            [],
            index,
            schema_provider=provider,
            retained_authority=retained,
            pre_workflow=workflow,
            pre_ui_payload=graph,
            schema_snapshot=payload,
        )


def test_malformed_retained_dataclass_nested_evidence_fails_before_preview() -> None:
    graph, provider, workflow, retained, index = _authority()
    malformed = replace(
        retained.schema,
        schemas={"A": {"class_type": "A", "inputs": [], "input_order": [], "outputs": [], "widget_input_order": [], "provenance": {}}},
    )
    forged_retained = AdmissionSnapshot(workflow=retained.workflow, schema=malformed)
    with pytest.raises(SchemaSnapshotError, match="malformed"):
        lint_delta(
            [],
            index,
            schema_provider=provider,
            retained_authority=forged_retained,
            pre_workflow=workflow,
            pre_ui_payload=graph,
            schema_snapshot=malformed,
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("ambient_lookup_forbidden", False),
        lambda payload: payload.__setitem__("workflow_observation_authoritative", True),
        lambda payload: payload.__setitem__("generation", "not-an-int"),
        lambda payload: payload["schemas"]["A"].__setitem__("inputs", "not-a-map"),
    ],
    ids=["ambient", "workflow-observation", "generation", "nested"],
)
def test_persisted_witness_rejects_before_submit_graph_reconstruction(mutate, monkeypatch) -> None:
    _graph, _provider, _workflow, retained, _index = _authority()
    payload = copy.deepcopy(schema_snapshot_to_payload(retained.schema))
    mutate(payload)
    called = []

    def should_not_reconstruct(*_args, **_kwargs):
        called.append(True)
        raise AssertionError("malformed witness reached workflow reconstruction")

    import vibecomfy.ingest.normalize as normalize
    monkeypatch.setattr(normalize, "from_ui", should_not_reconstruct)
    with pytest.raises(SchemaSnapshotError):
        snapshot_from_schema_witness(
            {"schema_snapshot": payload},
            submit_graph={"nodes": [], "links": []},
        )
    assert called == []


@pytest.mark.parametrize("witness", [None, {}, {"schema_snapshot": {}}, {"ambient_lookup_forbidden": False}])
def test_persisted_witness_absence_fails_at_authority_boundary(witness) -> None:
    with pytest.raises(SchemaSnapshotError):
        snapshot_from_schema_witness(witness, submit_graph={"nodes": [], "links": []})


def test_persisted_direct_and_wrapped_valid_witnesses_reconstruct() -> None:
    graph, _provider, _workflow, retained, _index = _authority()
    payload = schema_snapshot_to_payload(retained.schema)
    wrapped = snapshot_from_schema_witness({"schema_snapshot": payload}, submit_graph=graph)
    direct = snapshot_from_schema_witness(payload, submit_graph=graph)
    assert wrapped.schema is not None
    assert direct.schema is not None
    assert schema_snapshot_to_payload(wrapped.schema) == payload
    assert schema_snapshot_to_payload(direct.schema) == payload


@pytest.mark.parametrize("shape", ["typed", "tuple", "wrapped"])
def test_checked_pair_freezing_rejects_malformed_authority_even_for_empty_batch(shape) -> None:
    _graph, _provider, _workflow, retained, _index = _authority()
    malformed = replace(retained.schema, generation=-1)
    if shape == "typed":
        authority = malformed
    elif shape == "tuple":
        authority = (retained.workflow, malformed)
    else:
        authority = {"schema": {}, "schema_snapshot": schema_snapshot_to_payload(retained.schema)}
    with pytest.raises(SchemaSnapshotError):
        admit_operations(authority, [])


def test_checked_pair_freezing_preserves_legal_absent_schema_behavior() -> None:
    assert isinstance(admit_operations(None, []), AdmissionAllowed)
    assert isinstance(admit_operations((None, None), []), AdmissionAllowed)
    assert isinstance(admit_operations({"workflow": None, "schema": None}, []), AdmissionAllowed)


@pytest.mark.parametrize(
    "shape",
    [
        "null-wrapper",
        "empty-wrapper",
        "false-wrapper",
        "falsey-alias-does-not-fallback",
    ],
    ids=["null-wrapper", "empty-wrapper", "false-wrapper", "falsey-alias-does-not-fallback"],
)
def test_ops_authority_wrappers_fail_before_touched_schema_checks(shape) -> None:
    _graph, _provider, _workflow, retained, _index = _authority()
    authority = {
        "null-wrapper": {"schema_snapshot": None},
        "empty-wrapper": {"schema_snapshot": {}},
        "false-wrapper": {"schema_snapshot": False},
        "falsey-alias-does-not-fallback": {
            "schema": {},
            "schema_snapshot": schema_snapshot_to_payload(retained.schema),
        },
    }[shape]
    payload = {"op": "set_mode", "target": {"scope_path": "", "uid": "1"}, "mode": 2}
    with pytest.raises(EditOpParseError) as exc_info:
        parse_edit_op(payload, schema_snapshot=authority)
    assert exc_info.value.code in {"malformed_schema_snapshot", "ambient_lookup_forbidden"}


def test_ops_valid_direct_and_wrapped_authority_route_through_admission_once_and_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecomfy.porting.edit.admit as admit_module

    _graph, _provider, _workflow, retained, _index = _authority()
    payload = canonical_op_to_dict(_op())
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    real_admit_operation = admit_module.admit_operation

    def counted_admit_operation(*args: object, **kwargs: object):
        calls.append((args, kwargs))
        return real_admit_operation(*args, **kwargs)

    monkeypatch.setattr(admit_module, "admit_operation", counted_admit_operation)
    assert parse_edit_op(payload, schema_snapshot=retained.schema).op == "set_mode"
    assert len(calls) == 1
    calls.clear()
    assert parse_edit_op(
        payload,
        schema_snapshot={"schema_snapshot": schema_snapshot_to_payload(retained.schema)},
    ).op == "set_mode"
    assert len(calls) == 1


def test_frozen_add_replay_roundtrip_preserves_nested_payload_and_detaches() -> None:
    authored = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="vibecomfy.exec",
        fields={
            "source": "return {\"image\": image}",
            "io": {
                "inputs": [["image", "IMAGE"]],
                "outputs": [["image", "IMAGE"]],
                "metadata": {"nested": [1, {"kind": "IMAGE"}]},
            },
        },
        inputs={"in_0": LinkSourceRef("", "1", "IMAGE_0")},
        uid="n1",
        node_id="n1",
        widget_field_names=("io",),
    )
    frozen = _freeze_operation_tuple((authored,))[0]
    payload = canonical_op_to_dict(frozen)
    replay = parse_edit_op(payload)

    assert canonical_op_to_dict(replay) == payload
    assert accepted_delta_id((replay,)) == accepted_delta_id((frozen,))
    assert replay is not frozen
    assert replay.uid == "n1"
    assert replay.node_id == "n1"
    assert replay.widget_field_names == ("io",)
    assert replay.inputs["in_0"] == LinkSourceRef("", "1", "IMAGE_0")

    replay.fields["io"]["inputs"].append(["mask", "MASK"])
    assert canonical_op_to_dict(frozen)["fields"]["io"]["inputs"] == [["image", "IMAGE"]]
