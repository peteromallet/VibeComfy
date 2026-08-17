"""IR-path successor of the raw-JSON apply_delta suite.

Edits go through ``interpret``; UI is produced only at emit; the independent
exit guard validates that emit differs from the original only where the
accepted Δ attributes a change.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

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


def test_stage_apply_delta_fails_closed_when_exit_guard_rejects(monkeypatch, tmp_path) -> None:
    """A bad emit must reject the batch and stamp ui_fidelity_ok False."""
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext
    from vibecomfy.comfy_nodes.agent.edit import AgentEditState, _stage_apply_delta
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    from vibecomfy.porting.emit.ui import ExitGuardResult
    from vibecomfy.porting.report import PortIssue

    original = _fixture()
    state = AgentEditState(
        task="exit-guard-fail-closed",
        graph=original,
        guard_original_ui=original,
        request_payload={},
        schema_provider=_SchemaProvider(),
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
        session_dir=tmp_path,
        turn_dir=tmp_path / "turn_001",
        request_path=tmp_path / "request.json",
        original_ui_path=tmp_path / "original.json",
        before_py_path=tmp_path / "before.py",
        after_py_path=tmp_path / "after.py",
        projection_path=tmp_path / "projection.json",
        model_request_path=tmp_path / "model_request.json",
        model_response_path=tmp_path / "model_response.json",
        candidate_ui_path=tmp_path / "candidate.json",
        messages_path=tmp_path / "messages.json",
    )
    state.delta_ops = (
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="5", field_path="steps"),
            value=30,
        ),
    )

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

    result = _stage_apply_delta(
        state, TurnContext(session_id="guard-fail", turn_id="0001")
    )
    assert result.ok is False
    assert result.blocking is True
    assert result.gate_updates.get("ui_fidelity_ok") is False
    assert result.value.get("ui_fidelity_ok") is False
    assert getattr(state, "ui_payload", None) != result.value
    assert not (tmp_path / "candidate.json").exists()
    assert any(
        (issue.get("code") if isinstance(issue, dict) else getattr(issue, "code", None))
        == "full_ui_node_changed_unattributed"
        for issue in (result.issues or ())
    )
