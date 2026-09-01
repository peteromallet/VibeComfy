"""IR-path successor of the raw-JSON apply_delta suite.

Edits go through ``interpret``; UI is produced only at emit; the independent
exit guard validates that emit differs from the original only where the
accepted Δ attributes a change.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.emit.ui import guard_exit_ui
from vibecomfy.porting.edit.ops import parse_edit_delta
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec


class _SchemaProvider:
    def __init__(self) -> None:
        self._schemas = {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack="core",
                inputs={"ckpt_name": InputSpec(type="STRING", required=True)},
                outputs=[
                    OutputSpec(type="MODEL", name="MODEL"),
                    OutputSpec(type="CLIP", name="CLIP"),
                    OutputSpec(type="VAE", name="VAE"),
                ],
            ),
            "CLIPTextEncode": NodeSchema(
                class_type="CLIPTextEncode",
                pack="core",
                inputs={"text": InputSpec(type="STRING", required=True), "clip": InputSpec(type="CLIP", required=True)},
                outputs=[OutputSpec(type="CONDITIONING", name="CONDITIONING")],
            ),
            "KSampler": NodeSchema(
                class_type="KSampler",
                pack="core",
                inputs={
                    "seed": InputSpec(type="INT"),
                    "steps": InputSpec(type="INT", min=1, max=100),
                    "cfg": InputSpec(type="FLOAT", min=0.0, max=50.0),
                    "sampler_name": InputSpec(type="STRING", choices=["euler", "heun"]),
                    "scheduler": InputSpec(type="STRING", choices=["normal", "karras"]),
                    "denoise": InputSpec(type="FLOAT", min=0.0, max=1.0),
                    "model": InputSpec(type="MODEL", required=True),
                    "positive": InputSpec(type="CONDITIONING", required=True),
                    "negative": InputSpec(type="CONDITIONING", required=True),
                    "latent_image": InputSpec(type="LATENT", required=True),
                },
                outputs=[OutputSpec(type="LATENT", name="LATENT")],
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack="core",
                inputs={
                    "images": InputSpec(type="IMAGE", required=True),
                    "filename_prefix": InputSpec(type="STRING", required=True),
                },
                outputs=[],
            ),
        }

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _fixture(name: str = "flat.json") -> dict[str, object]:
    path = Path("tests/fixtures/agent_edit") / name
    return json.loads(path.read_text(encoding="utf-8"))


def _interpret(ui, ops, provider=None):
    provider = provider or _SchemaProvider()
    workflow = from_ui(dict(ui), schema_provider=provider, use_comfy_converter=False)
    return interpret(workflow, tuple(ops), schema_provider=provider)


def _node_by_uid(workflow, uid: str):
    for node in workflow.nodes.values():
        if str(getattr(node, "uid", "") or "") == uid:
            return node
    return None


def _append_uidless_node_and_edge(
    workflow,
    *,
    to_node: str = "7",
    to_input: str = "images",
):
    node = copy.deepcopy(workflow.nodes["6"])
    node.id = "999"
    node.uid = ""
    workflow.nodes["999"] = node
    edge = copy.deepcopy(workflow.edges[-1])
    edge.from_node = "999"
    edge.from_output = "IMAGE"
    edge.to_node = to_node
    edge.to_input = to_input
    workflow.edges.append(edge)
    return edge


def _append_duplicate_edge(workflow) -> None:
    workflow.edges.append(copy.deepcopy(workflow.edges[0]))


def test_interpret_rejects_unknown_target_without_mutating_original() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "no-such-uid", "steps"], "value": 8}]
    )
    result = _interpret(original, delta)
    assert result.ok is False
    assert original == before


def test_interpret_rejects_unknown_link_endpoint_without_mutating_original() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    delta = parse_edit_delta(
        [{"op": "upsert_link", "from": ["", "no-such-uid", "MODEL"], "to": ["", "5", "model"]}]
    )
    result = _interpret(original, delta)
    assert result.ok is False
    assert original == before


def test_interpret_sets_ksampler_steps() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    result = _interpret(original, delta)
    assert result.ok is True
    assert original == before
    node = _node_by_uid(result.workflow, "5")
    assert node is not None
    value = (node.widgets or {}).get("steps")
    if value is None:
        value = (node.inputs or {}).get("steps")
    assert value == 42


def test_interpret_sets_mode() -> None:
    original = _fixture()
    delta = parse_edit_delta([{"op": "set_mode", "target": ["", "5"], "mode": 2}])
    result = _interpret(original, delta)
    assert result.ok is True
    node = _node_by_uid(result.workflow, "5")
    assert node is not None
    from vibecomfy.workflow import mode_to_litegraph

    assert mode_to_litegraph(node.mode) == 2


def test_interpret_rejects_legacy_set_title_and_reorder() -> None:
    with __import__("pytest").raises(Exception):
        parse_edit_delta([{"op": "set_title", "target": ["", "5"], "title": "nope"}])
    with __import__("pytest").raises(Exception):
        parse_edit_delta([{"op": "reorder", "uids": ["5", "4"]}])


def test_interpret_adds_node_and_emit_is_usable() -> None:
    original = _fixture()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "SaveImage",
                "fields": {"filename_prefix": "after"},
            }
        ]
    )
    result = _interpret(original, delta)
    assert result.ok is True
    added = [node for node in result.workflow.nodes.values() if node.class_type == "SaveImage"]
    assert added
    emitted = emit_ui_json(
        result.workflow,
        schema_provider=_SchemaProvider(),
        include_virtual_wires=True,
        prior_ui_payload=original,
    )
    assert isinstance(emitted.get("nodes"), list)
    assert any(
        str((node.get("properties") or {}).get("vibecomfy_uid") or "") == str(getattr(added[0], "uid", ""))
        or node.get("type") == "SaveImage"
        for node in emitted["nodes"]
        if isinstance(node, dict)
    )


def test_apply_gate_replays_python_source_for_unknown_schema_add_node() -> None:
    """Python add-node source preserves the IR channel for unknown schemas."""
    from vibecomfy.porting.edit.apply_gate import verify_apply
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    original = {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "SourceOne",
                "mode": 0,
                "pos": [0, 0],
                "size": [210, 58],
                "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                "properties": {"vibecomfy_uid": "src"},
            }
        ],
        "links": [],
    }

    class _UnknownProvider:
        def get_schema(self, class_type: str):
            if class_type == "UnknownSampler":
                return NodeSchema(
                    "UnknownSampler",
                    None,
                    {
                        "seed": InputSpec(type="INT"),
                        "options": InputSpec(type="*"),
                    },
                    [OutputSpec(type="LATENT", name="LATENT")],
                )
            return None

    provider = _UnknownProvider()
    session = EditSession(original, schema_provider=provider)
    source = 'sampler = UnknownSampler(seed=40 + 2, options={"scale": 2 * 4})\n'
    pre = session.workflow.copy()
    interpreted = interpret(pre, source, schema_provider=provider)
    assert interpreted.ok is True
    gate = verify_apply(
        pre,
        interpreted.workflow,
        delta=source,
        landed_ops=interpreted.landed_ops,
        schema_provider=provider,
    )
    assert gate.ok is True
    assert gate.apply_eligible is True


def test_interpret_remove_node_drops_ir_node() -> None:
    original = _fixture()
    delta = parse_edit_delta([{"op": "remove_node", "target": ["", "7"]}])
    result = _interpret(original, delta)
    assert result.ok is True
    assert _node_by_uid(result.workflow, "7") is None


def test_interpret_upsert_link_rewires_in_ir() -> None:
    original = _fixture()
    delta = parse_edit_delta(
        [{"op": "upsert_link", "from": ["", "4", "LATENT"], "to": ["", "5", "latent_image"]}]
    )
    result = _interpret(original, delta)
    assert result.ok is True
    dest = _node_by_uid(result.workflow, "5")
    assert dest is not None
    dest_id = str(dest.id)
    matching = [
        edge
        for edge in result.workflow.edges
        if str(getattr(edge, "to_node", "")) == dest_id
        and str(getattr(edge, "to_input", "")) == "latent_image"
    ]
    assert matching


def test_guard_exit_ui_passes_identity() -> None:
    original = _fixture()
    guard = guard_exit_ui(original, copy.deepcopy(original), ())
    assert guard.ok is True


def test_guard_exit_ui_refuses_unattributed_node_change() -> None:
    original = _fixture()
    for node in original.get("nodes") or []:
        if isinstance(node, dict):
            props = node.setdefault("properties", {})
            if isinstance(props, dict) and not props.get("vibecomfy_uid"):
                props["vibecomfy_uid"] = str(node.get("id"))
    candidate = copy.deepcopy(original)
    nodes = candidate.get("nodes")
    assert isinstance(nodes, list) and nodes
    first = nodes[0]
    assert isinstance(first, dict)
    first["title"] = "unattributed-title"
    guard = guard_exit_ui(original, candidate, ())
    assert guard.ok is False
    assert any(issue.code == "full_ui_node_changed_unattributed" for issue in guard.diagnostics)


def test_guard_exit_ui_accepts_attributed_field_change() -> None:
    original = _fixture()
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 30}]
    )
    result = _interpret(original, delta)
    assert result.ok is True
    emitted = emit_ui_json(
        result.workflow,
        schema_provider=_SchemaProvider(),
        include_virtual_wires=True,
        prior_ui_payload=original,
    )
    guard = guard_exit_ui(original, emitted, result.landed_ops)
    # Emit may change furniture (ids/version); attributed node field must not
    # be reported as an unattributed node change.
    unattributed_nodes = [
        issue
        for issue in guard.diagnostics
        if issue.code == "full_ui_node_changed_unattributed"
        and (issue.detail or {}).get("uid") == "5"
    ]
    assert unattributed_nodes == []


def test_guard_exit_ui_rejects_unrelated_widget_change_on_attributed_node() -> None:
    original = _fixture()
    candidate = copy.deepcopy(original)
    sampler = next(node for node in candidate["nodes"] if node["id"] == 5)
    sampler["widgets_values"][2] = 30
    sampler["widgets_values"][3] = 12
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 30}]
    )

    guard = guard_exit_ui(original, candidate, delta)

    assert guard.ok is False
    assert any(
        issue.code == "full_ui_node_changed_unattributed"
        and (issue.detail or {}).get("uid") == "5"
        and "widgets_values[3]" in (issue.detail or {}).get("field_paths", [])
        for issue in guard.diagnostics
    )


def test_guard_exit_ui_rejects_arbitrary_uid_rewrite() -> None:
    original = _fixture()
    candidate = copy.deepcopy(original)
    sampler = next(node for node in candidate["nodes"] if node["id"] == 5)
    sampler.setdefault("properties", {})["vibecomfy_uid"] = "unrelated-identity"

    guard = guard_exit_ui(original, candidate, ())

    assert guard.ok is False
    assert any(
        issue.code in {
            "full_ui_node_removed_unattributed",
            "full_ui_node_added_unattributed",
        }
        for issue in guard.diagnostics
    )


def test_apply_delta_stops_before_mutation_for_invalid_delta() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "missing-uid", "steps"], "value": 8}]
    )
    result = _interpret(original, delta)
    assert result.ok is False
    assert original == before


def test_resolve_delta_rejects_unknown_remove_target_before_any_mutation() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    delta = parse_edit_delta([{"op": "remove_node", "target": ["", "missing-uid"]}])
    result = _interpret(original, delta)
    assert result.ok is False
    assert original == before


def test_interpret_emit_fails_closed_when_exit_guard_rejects(monkeypatch) -> None:
    """A bad emit must reject via the live interpret + emit-guard path.

    Mutation authority is interpret; UI is an emit-side projection; the
    independent ``guard_exit_ui`` is the hard gate on ``EditSession.done``.
    A rejected guard is not done and does not treat the candidate as
    published.  The ingest snapshot is never mutated.
    """
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.porting.emit.ui import ExitGuardResult
    from vibecomfy.porting.report import PortIssue

    original = _fixture()
    before = copy.deepcopy(original)
    session = EditSession(original, schema_provider=_SchemaProvider())
    batch = session.apply_batch("ksampler.steps = 30\n")
    assert batch.ok, batch.diagnostics
    assert session.original_ui == before

    monkeypatch.setattr(
        "vibecomfy.porting.emit.ui.guard_exit_ui",
        lambda *args, **kwargs: ExitGuardResult(
            ok=False,
            diagnostics=(
                PortIssue(
                    code="full_ui_node_changed_unattributed",
                    message="unattributed emit change",
                    severity="error",
                ),
            ),
        ),
    )

    done = session.done()
    assert done.ok is False
    assert any(
        getattr(diag, "code", None) == "full_ui_node_changed_unattributed"
        for diag in done.diagnostics
    )
    assert "emit-exit guard rejected" in done.summary
    assert session.original_ui == before


def test_apply_gate_rejects_new_self_loop_as_not_eligible() -> None:
    """B4 S4 shape: a newly created u→u edge must not be apply-eligible."""
    from vibecomfy.porting.edit.apply_gate import apply_eligible_for, verify_apply
    from vibecomfy.porting.edit.session import EditSession

    original = _fixture()
    provider = _SchemaProvider()
    pre = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    delta = parse_edit_delta(
        [{"op": "upsert_link", "from": ["", "5", "LATENT"], "to": ["", "5", "latent_image"]}]
    )
    interpreted = interpret(pre, delta, schema_provider=provider)
    assert interpreted.ok is True
    assert interpreted.landed_ops
    gate = verify_apply(
        pre,
        interpreted.workflow,
        delta=delta,
        landed_ops=interpreted.landed_ops,
        schema_provider=provider,
    )
    assert gate.ok is False
    assert gate.apply_eligible is False
    assert apply_eligible_for(gate) is False
    assert gate.reason == "new_self_loop"
    assert any(item.code == "apply_gate_new_self_loop" for item in gate.diagnostics)

    session = EditSession(original, schema_provider=provider)
    batch = session.apply_batch("ksampler.latent_image = ksampler.LATENT\n")
    assert batch.ok is False
    assert batch.apply_eligible is False
    assert batch.landed_ops == ()
    assert any(item.code == "apply_gate_new_self_loop" for item in batch.diagnostics)
    retained = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    assert editable_uids(session.workflow) == editable_uids(retained)
    assert not any(
        str(edge.from_node) == str(edge.to_node) for edge in session.workflow.edges
    )


def test_apply_gate_allows_legal_widget_edit() -> None:
    from vibecomfy.porting.edit.apply_gate import apply_eligible_for, verify_apply
    from vibecomfy.porting.edit.session import EditSession

    original = _fixture()
    provider = _SchemaProvider()
    pre = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    interpreted = interpret(pre, delta, schema_provider=provider)
    assert interpreted.ok is True
    gate = verify_apply(
        pre,
        interpreted.workflow,
        delta=delta,
        landed_ops=interpreted.landed_ops,
        schema_provider=provider,
    )
    assert gate.ok is True
    assert gate.apply_eligible is True
    assert apply_eligible_for(gate) is True

    session = EditSession(original, schema_provider=provider)
    batch = session.apply_batch("ksampler.steps = 42\n")
    assert batch.ok is True
    assert batch.apply_eligible is True
    assert batch.landed_ops
    node = _node_by_uid(session.workflow, "5")
    assert node is not None
    value = (node.widgets or {}).get("steps")
    if value is None:
        value = (node.inputs or {}).get("steps")
    assert value == 42


def test_apply_gate_rejects_unclaimed_semantic_edge_mismatches() -> None:
    """Link-ID furniture must never excuse a different canonical edge."""
    from vibecomfy.porting.edit.apply_gate import verify_apply

    original = _fixture()
    provider = _SchemaProvider()
    pre = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    interpreted = interpret(pre, delta, schema_provider=provider)
    assert interpreted.ok is True
    assert interpreted.landed_ops

    def changed_post(kind: str):
        post = copy.deepcopy(interpreted.workflow)
        edge = post.edges[0]
        if kind == "source_node":
            edge.from_node = "3"
        elif kind == "source_slot":
            edge.from_output = "CLIP"
        elif kind == "destination_node":
            edge.to_node = "6"
        elif kind == "destination_slot":
            edge.to_input = "positive"
        elif kind == "add":
            added = copy.deepcopy(edge)
            added.to_node = "7"
            added.to_input = "images"
            post.edges.append(added)
        elif kind == "remove":
            post.edges.pop(0)
        else:  # pragma: no cover - closed test table
            raise AssertionError(f"unknown edge mutation {kind}")
        return post

    for kind in (
        "source_node",
        "source_slot",
        "destination_node",
        "destination_slot",
        "add",
        "remove",
    ):
        gate = verify_apply(
            pre,
            changed_post(kind),
            delta=delta,
            landed_ops=interpreted.landed_ops,
            schema_provider=provider,
        )
        assert gate.ok is False, kind
        assert gate.apply_eligible is False, kind
        assert gate.reason == "replay_mismatch", kind
        assert any(
            item.code == "apply_gate_replay_mismatch" for item in gate.diagnostics
        ), kind


def test_apply_gate_fails_closed_on_unverifiable_identity_and_edge_multiplicity() -> None:
    """Every node/endpoint must resolve uniquely and edge counts must replay."""
    from vibecomfy.porting.edit.apply_gate import verify_apply

    provider = _SchemaProvider()
    pre = from_ui(
        _fixture(),
        schema_provider=provider,
        use_comfy_converter=False,
    )
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    interpreted = interpret(pre, delta, schema_provider=provider)
    assert interpreted.ok is True
    assert interpreted.landed_ops

    uidless_add = copy.deepcopy(interpreted.workflow)
    _append_uidless_node_and_edge(uidless_add)

    uidless_pre = copy.deepcopy(pre)
    _append_uidless_node_and_edge(uidless_pre)
    uidless_retarget = copy.deepcopy(interpreted.workflow)
    _append_uidless_node_and_edge(
        uidless_retarget,
        to_node="6",
        to_input="samples",
    )

    duplicate_uid = copy.deepcopy(interpreted.workflow)
    duplicate_uid_node = copy.deepcopy(duplicate_uid.nodes["7"])
    duplicate_uid_node.id = "999"
    duplicate_uid.nodes["999"] = duplicate_uid_node

    unresolved_endpoint = copy.deepcopy(interpreted.workflow)
    dangling_edge = copy.deepcopy(unresolved_endpoint.edges[-1])
    dangling_edge.from_node = "999"
    unresolved_endpoint.edges.append(dangling_edge)

    duplicate_add = copy.deepcopy(interpreted.workflow)
    _append_duplicate_edge(duplicate_add)

    duplicate_pre = copy.deepcopy(pre)
    _append_duplicate_edge(duplicate_pre)
    duplicate_remove = copy.deepcopy(interpreted.workflow)

    identity_cases = (
        ("uidless_node_edge_addition", pre, uidless_add),
        ("uidless_endpoint_retarget", uidless_pre, uidless_retarget),
        ("duplicate_node_uid", pre, duplicate_uid),
        ("unresolvable_edge_endpoint", pre, unresolved_endpoint),
    )
    for kind, case_pre, case_post in identity_cases:
        gate = verify_apply(
            case_pre,
            case_post,
            delta=delta,
            landed_ops=interpreted.landed_ops,
            schema_provider=provider,
        )
        assert gate.ok is False, kind
        assert gate.apply_eligible is False, kind
        assert gate.reason == "unverifiable_identity", kind
        assert any(
            item.code == "apply_gate_unverifiable_identity"
            for item in gate.diagnostics
        ), kind

    multiplicity_cases = (
        ("duplicate_edge_addition", pre, duplicate_add, "only_in_post"),
        (
            "duplicate_edge_removal",
            duplicate_pre,
            duplicate_remove,
            "only_in_replay",
        ),
    )
    for kind, case_pre, case_post, delta_side in multiplicity_cases:
        gate = verify_apply(
            case_pre,
            case_post,
            delta=delta,
            landed_ops=interpreted.landed_ops,
            schema_provider=provider,
        )
        assert gate.ok is False, kind
        assert gate.apply_eligible is False, kind
        assert gate.reason == "replay_mismatch", kind
        mismatch = next(
            item
            for item in gate.diagnostics
            if item.code == "apply_gate_replay_mismatch"
        )
        assert len(mismatch.detail["edge_delta"][delta_side]) == 1, kind


@pytest.mark.parametrize(
    ("mutation", "diagnostic_code"),
    (
        ("uidless_node_edge_addition", "apply_gate_unverifiable_identity"),
        ("uidless_endpoint_retarget", "apply_gate_unverifiable_identity"),
        ("duplicate_edge_addition", "apply_gate_replay_mismatch"),
        ("duplicate_edge_removal", "apply_gate_replay_mismatch"),
    ),
)
def test_apply_batch_replay_rejection_is_atomic(
    monkeypatch,
    mutation: str,
    diagnostic_code: str,
) -> None:
    """Replay-ineligible candidates cannot cross the Python commit boundary."""
    from vibecomfy.porting.edit import _interpret
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    if mutation == "uidless_endpoint_retarget":
        _append_uidless_node_and_edge(session.workflow)
    elif mutation == "duplicate_edge_removal":
        _append_duplicate_edge(session.workflow)
    before = copy.deepcopy(session.workflow)
    original_interpret = _interpret.interpret
    call_count = 0

    def injected_candidate(*args, **kwargs):
        nonlocal call_count
        result = original_interpret(*args, **kwargs)
        call_count += 1
        if call_count != 1 or not result.ok:
            return result
        if mutation == "uidless_node_edge_addition":
            _append_uidless_node_and_edge(result.workflow)
        elif mutation == "uidless_endpoint_retarget":
            uidless_edge = next(
                edge
                for edge in result.workflow.edges
                if str(edge.from_node) == "999"
            )
            uidless_edge.to_node = "6"
            uidless_edge.to_input = "samples"
        elif mutation == "duplicate_edge_addition":
            _append_duplicate_edge(result.workflow)
        elif mutation == "duplicate_edge_removal":
            first = result.workflow.edges[0]
            duplicate_index = next(
                index
                for index, edge in enumerate(result.workflow.edges[1:], start=1)
                if edge == first
            )
            result.workflow.edges.pop(duplicate_index)
        else:  # pragma: no cover - closed parametrization
            raise AssertionError(mutation)
        return result

    monkeypatch.setattr(_interpret, "interpret", injected_candidate)
    batch = session.apply_batch("ksampler.steps = 42\n")

    assert batch.ok is False
    assert batch.apply_eligible is False
    assert batch.landed_ops == ()
    assert any(item.code == diagnostic_code for item in batch.diagnostics)
    assert session.revision == 0
    assert session.history == []
    assert session.landed_ops == []
    assert session.workflow == before


@pytest.mark.parametrize(
    ("mutation", "diagnostic_code"),
    (
        ("uidless_node_edge_addition", "apply_gate_unverifiable_identity"),
        ("duplicate_edge_addition", "apply_gate_replay_mismatch"),
    ),
)
def test_apply_ops_replay_rejection_is_atomic(
    monkeypatch,
    mutation: str,
    diagnostic_code: str,
) -> None:
    """Typed apply_ops rejects an unverifiable candidate before any commit."""
    from vibecomfy.porting.edit import _op_validate
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    before = copy.deepcopy(session.workflow)
    before_ui = copy.deepcopy(session.working_ui)
    original_validate = _op_validate.validate_typed_ops

    def injected_candidate(*args, **kwargs):
        post = original_validate(*args, **kwargs)
        if mutation == "uidless_node_edge_addition":
            _append_uidless_node_and_edge(post)
        elif mutation == "duplicate_edge_addition":
            _append_duplicate_edge(post)
        else:  # pragma: no cover - closed parametrization
            raise AssertionError(mutation)
        return post

    monkeypatch.setattr(_op_validate, "validate_typed_ops", injected_candidate)
    ops = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    result = session.apply_ops(ops, expected_revision=0)

    assert result.ok is False
    assert result.reason == "verification_failed"
    assert result.revision == 0
    assert result.landed_ops == ()
    assert any(item.code == diagnostic_code for item in result.diagnostics)
    assert session.revision == 0
    assert session.history == []
    assert session.landed_ops == []
    assert session.workflow == before
    assert session.working_ui == before_ui


def test_apply_batch_empty_delta_gate_is_atomic(monkeypatch) -> None:
    """An ok gate with no eligible delta cannot cross the batch commit boundary."""
    from vibecomfy.porting.edit import apply_gate
    from vibecomfy.porting.edit.apply_gate import ApplyGateResult
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    before = copy.deepcopy(session.workflow)
    before_ui = copy.deepcopy(session.working_ui)

    monkeypatch.setattr(
        apply_gate,
        "verify_apply",
        lambda *args, **kwargs: ApplyGateResult(
            ok=True,
            apply_eligible=False,
            reason="empty_delta",
        ),
    )

    result = session.apply_batch("ksampler.steps = 42\n")

    assert result.ok is False
    assert result.apply_eligible is False
    assert result.landed_ops == ()
    assert session.revision == 0
    assert session.history == []
    assert session.landed_ops == []
    assert session.workflow == before
    assert session.working_ui == before_ui


def test_apply_batch_subgraph_interface_is_a_replayable_delta() -> None:
    """B13: interface-only edits are non-empty and may cross the apply gate."""
    from vibecomfy.porting.edit.session import EditSession

    session = EditSession(
        {"last_node_id": 0, "last_link_id": 0, "nodes": [], "links": [], "groups": []}
    )

    result = session.apply_batch(
        "subgraph_interface("
        "name='Only', id='only', "
        "inputs=(('in', 'IMAGE'),), outputs=(('out', 'IMAGE'),))\n"
    )

    assert result.ok is True
    assert result.apply_eligible is True
    assert len(session.history) == 1
    assert session.done().ok is True

def test_apply_batch_failed_interpretation_ineligible_gate_is_atomic(monkeypatch) -> None:
    """A failed interpretation cannot commit an ineligible candidate."""
    from vibecomfy.porting.edit import _interpret, apply_gate
    from vibecomfy.porting.edit.apply_gate import ApplyGateResult
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    before = copy.deepcopy(session.workflow)
    before_ui = copy.deepcopy(session.working_ui)
    original_interpret = _interpret.interpret

    def failed_interpret(*args, **kwargs):
        interpreted = original_interpret(*args, **kwargs)
        assert interpreted.ok is True
        return replace(interpreted, ok=False)

    monkeypatch.setattr(_interpret, "interpret", failed_interpret)
    monkeypatch.setattr(
        apply_gate,
        "verify_apply",
        lambda *args, **kwargs: ApplyGateResult(
            ok=True,
            apply_eligible=False,
            reason="empty_delta",
        ),
    )

    result = session.apply_batch("ksampler.steps = 42\n")

    assert result.ok is False
    assert result.apply_eligible is False
    assert result.landed_ops == ()
    assert session.revision == 0
    assert session.history == []
    assert session.landed_ops == []
    assert session.workflow == before
    assert session.working_ui == before_ui


def test_apply_batch_failed_interpretation_rejected_gate_is_atomic(monkeypatch) -> None:
    """A failed interpretation still rejects a corrupt candidate atomically."""
    from vibecomfy.porting.edit import _interpret, apply_gate
    from vibecomfy.porting.edit.apply_gate import ApplyGateResult
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    before = copy.deepcopy(session.workflow)
    before_ui = copy.deepcopy(session.working_ui)
    original_interpret = _interpret.interpret

    def failed_interpret(*args, **kwargs):
        interpreted = original_interpret(*args, **kwargs)
        assert interpreted.ok is True
        return replace(interpreted, ok=False)

    monkeypatch.setattr(_interpret, "interpret", failed_interpret)
    monkeypatch.setattr(
        apply_gate,
        "verify_apply",
        lambda *args, **kwargs: ApplyGateResult(
            ok=False,
            apply_eligible=False,
            reason="replay_mismatch",
        ),
    )

    result = session.apply_batch("ksampler.steps = 42\n")

    assert result.ok is False
    assert result.apply_eligible is False
    assert result.landed_ops == ()
    assert session.revision == 0
    assert session.history == []
    assert session.landed_ops == []
    assert session.workflow == before
    assert session.working_ui == before_ui


def test_apply_ops_empty_delta_gate_is_atomic(monkeypatch) -> None:
    """Typed apply rejects an ineligible empty delta before committing."""
    from vibecomfy.porting.edit import apply_gate
    from vibecomfy.porting.edit.apply_gate import ApplyGateResult
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    before = copy.deepcopy(session.workflow)
    before_ui = copy.deepcopy(session.working_ui)
    ops = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )

    monkeypatch.setattr(
        apply_gate,
        "verify_apply",
        lambda *args, **kwargs: ApplyGateResult(
            ok=True,
            apply_eligible=False,
            reason="empty_delta",
        ),
    )

    result = session.apply_ops(ops, expected_revision=0)

    assert result.ok is False
    assert result.reason == "verification_failed"
    assert result.landed_ops == ()
    assert result.revision == 0
    assert session.revision == 0
    assert session.history == []
    assert session.landed_ops == []
    assert session.workflow == before
    assert session.working_ui == before_ui


def test_done_empty_delta_is_observational() -> None:
    """done() verifies an empty session without creating commit state."""
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    before = copy.deepcopy(session.workflow)
    before_ui = copy.deepcopy(session.working_ui)

    result = session.done()

    assert result.ok is True
    assert session.revision == 0
    assert session.history == []
    assert session.landed_ops == []
    assert session.workflow == before
    assert session.working_ui == before_ui



def test_done_rejection_does_not_advance_commit_state() -> None:
    """A post-apply replay failure is terminal without a second commit."""
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    accepted = session.apply_batch("ksampler.steps = 42\n")
    assert accepted.ok is True
    revision = session.revision
    history = copy.deepcopy(session.history)
    _append_duplicate_edge(session.workflow)

    done = session.done()

    assert done.ok is False
    assert session.revision == revision
    assert session.history == history


def test_apply_batch_accepts_edge_order_and_layout_furniture(monkeypatch) -> None:
    """Edge order and node geometry remain outside replay equivalence."""
    from vibecomfy.porting.edit import _interpret
    from vibecomfy.porting.edit.session import EditSession

    provider = _SchemaProvider()
    session = EditSession(_fixture(), schema_provider=provider)
    before = copy.deepcopy(session.workflow)
    original_interpret = _interpret.interpret
    call_count = 0

    def furniture_candidate(*args, **kwargs):
        nonlocal call_count
        result = original_interpret(*args, **kwargs)
        call_count += 1
        if call_count == 1 and result.ok:
            result.workflow.edges.reverse()
            result.workflow.nodes["5"].pos = [999.0, 1001.0]
            result.workflow.nodes["5"].size = [333.0, 444.0]
        return result

    monkeypatch.setattr(_interpret, "interpret", furniture_candidate)
    batch = session.apply_batch("ksampler.steps = 42\n")

    assert batch.ok is True
    assert batch.apply_eligible is True
    assert session.revision == 1
    assert len(session.history) == 1
    assert session.workflow.edges == list(reversed(before.edges))
    assert session.workflow.nodes["5"].pos == [999.0, 1001.0]
    assert session.workflow.nodes["5"].size == [333.0, 444.0]


def test_apply_gate_allows_runtime_link_id_renumbering() -> None:
    """Raw link IDs/counters are furniture when canonical endpoints match."""
    from vibecomfy.porting.edit.apply_gate import editable_signature, verify_apply

    original = _fixture()
    provider = _SchemaProvider()
    pre = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    interpreted = interpret(pre, delta, schema_provider=provider)
    assert interpreted.ok is True
    assert interpreted.landed_ops

    renumbered = copy.deepcopy(original)
    sampler = next(node for node in renumbered["nodes"] if node["id"] == 5)
    sampler["widgets_values"][2] = 42
    link_ids = {link[0]: link[0] + 100 for link in renumbered["links"]}
    for link in renumbered["links"]:
        link[0] = link_ids[link[0]]
    for node in renumbered["nodes"]:
        for input_slot in node.get("inputs", ()):
            if input_slot.get("link") in link_ids:
                input_slot["link"] = link_ids[input_slot["link"]]
        for output_slot in node.get("outputs", ()):
            output_slot["links"] = [
                link_ids[link_id] for link_id in output_slot.get("links") or ()
            ]
    renumbered["last_link_id"] = max(link_ids.values())
    post = from_ui(
        renumbered,
        schema_provider=provider,
        use_comfy_converter=False,
    )

    assert renumbered["links"][0][0] != original["links"][0][0]
    assert editable_signature(post) == editable_signature(interpreted.workflow)
    gate = verify_apply(
        pre,
        post,
        delta=delta,
        landed_ops=interpreted.landed_ops,
        schema_provider=provider,
    )
    assert gate.ok is True
    assert gate.apply_eligible is True


def test_apply_gate_accepts_emitted_link_removal_and_renumbering() -> None:
    """Semantic link removal is valid; its emitted ID is only furniture."""
    from vibecomfy.porting.edit.apply_gate import verify_apply

    original = _fixture()
    provider = _SchemaProvider()
    pre = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    delta = parse_edit_delta(
        [{"op": "remove_link", "to": ["", "5", "latent_image"]}]
    )
    interpreted = interpret(pre, delta, schema_provider=provider)
    assert interpreted.ok is True
    emitted = emit_ui_json(
        interpreted.workflow,
        schema_provider=provider,
        include_virtual_wires=True,
        prior_ui_payload=original,
    )
    assert len(emitted["links"]) == len(original["links"]) - 1
    emitted["last_link_id"] = 0
    post = from_ui(
        emitted,
        schema_provider=provider,
        use_comfy_converter=False,
    )
    gate = verify_apply(
        pre,
        post,
        delta=delta,
        landed_ops=interpreted.landed_ops,
        schema_provider=provider,
    )
    assert gate.ok is True
    assert gate.apply_eligible is True


def test_apply_gate_does_not_waive_semantic_mismatch_for_counter_decrease() -> None:
    """Emitter counters cannot authorize a changed canonical edge."""
    from vibecomfy.porting.edit.apply_gate import verify_apply

    original = _fixture()
    provider = _SchemaProvider()
    pre = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    interpreted = interpret(pre, delta, schema_provider=provider)
    assert interpreted.ok is True
    emitted = emit_ui_json(
        interpreted.workflow,
        schema_provider=provider,
        include_virtual_wires=True,
        prior_ui_payload=original,
    )
    emitted["last_link_id"] = 0
    # Keep the link shape valid while changing its semantic source endpoint.
    emitted["links"][0][1] = 3
    post = from_ui(
        emitted,
        schema_provider=provider,
        use_comfy_converter=False,
    )
    gate = verify_apply(
        pre,
        post,
        delta=delta,
        landed_ops=interpreted.landed_ops,
        schema_provider=provider,
    )
    assert gate.ok is False
    assert gate.apply_eligible is False
    assert gate.reason == "replay_mismatch"
    assert any(
        item.code == "apply_gate_replay_mismatch" for item in gate.diagnostics
    )

def test_apply_gate_empty_replay_is_not_eligible() -> None:
    from vibecomfy.porting.edit.apply_gate import verify_apply

    original = _fixture()
    provider = _SchemaProvider()
    pre = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    interpreted = interpret(pre, delta, schema_provider=provider)
    assert interpreted.landed_ops
    gate = verify_apply(
        pre,
        pre,
        delta=delta,
        landed_ops=interpreted.landed_ops,
        schema_provider=provider,
    )
    assert gate.apply_eligible is False
    assert gate.reason == "empty_delta"


def test_interpret_pre_delta_reconstructs_post() -> None:
    from vibecomfy.porting.edit.apply_gate import editable_signature

    original = _fixture()
    provider = _SchemaProvider()
    pre = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 42}]
    )
    first = interpret(pre, delta, schema_provider=provider)
    assert first.ok is True
    replayed = interpret(pre, first.landed_ops, schema_provider=provider)
    assert replayed.ok is True
    assert editable_signature(replayed.workflow) == editable_signature(first.workflow)


def editable_uids(workflow) -> set[str]:
    return {
        str(node.uid)
        for node in workflow.nodes.values()
        if getattr(node, "uid", None)
    }
