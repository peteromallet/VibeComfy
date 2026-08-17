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
