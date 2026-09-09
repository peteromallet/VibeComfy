"""Tests for vibecomfy.porting.edit.lint — lint_delta() behaviour.

Coverage:
- canonical uid pass-through
- LiteGraph id → canonical uid rewrite
- unknown target rejection
- field no-op drop
- mode no-op drop
- absent field rejection
- identity rewrite pass-through (sequence with mixed outcomes)
- add_node class_type / scope validation
- upsert_link uid resolution
- remove_link link-id and target-based validation
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.porting.edit.lint import (
    LintIndex,
    LintResult,
    lint_delta as _production_lint_delta,
)
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _fixture(name: str) -> dict[str, Any]:
    path = Path("tests/fixtures/agent_edit") / name
    return json.loads(path.read_text(encoding="utf-8"))


def _index(name: str = "flat.json") -> LintIndex:
    return LintIndex.build(_fixture(name))


# Unit cases exercise the public lint entry point against raw fixture UI, while
# the schema authority is an independently declared test provider.  The
# provider is deliberately not synthesized from node ``inputs``/``outputs``:
# those are presentation evidence and are not schema authority.


def _declared_schemas():
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    def _schema(class_type, inputs=(), outputs=()):
        return NodeSchema(
            class_type=class_type,
            pack="test",
            inputs={name: InputSpec(type=socket) for name, socket in inputs},
            outputs=[OutputSpec(name=name, type=socket) for name, socket in outputs],
        )

    return {
        "CheckpointLoaderSimple": _schema(
            "CheckpointLoaderSimple",
            outputs=(("MODEL", "MODEL"), ("CLIP", "CLIP"), ("VAE", "VAE")),
        ),
        "CLIPTextEncode": _schema(
            "CLIPTextEncode",
            inputs=(("clip", "CLIP"),),
            outputs=(("CONDITIONING", "CONDITIONING"),),
        ),
        "EmptyLatentImage": _schema(
            "EmptyLatentImage", outputs=(("LATENT", "LATENT"),)
        ),
        "KSampler": _schema(
            "KSampler",
            inputs=(
                ("model", "MODEL"),
                ("positive", "CONDITIONING"),
                ("negative", "CONDITIONING"),
                ("latent_image", "LATENT"),
            ),
            outputs=(("LATENT", "LATENT"),),
        ),
        "VAEDecode": _schema(
            "VAEDecode",
            inputs=(("samples", "LATENT"), ("vae", "VAE")),
            outputs=(("IMAGE", "IMAGE"),),
        ),
        "SaveImage": _schema(
            "SaveImage", inputs=(("images", "IMAGE"),)
        ),
        # Fixture-only custom classes used by focused lint tests.
        "Src": _schema("Src", outputs=(("out", "*"),)),
        "Dst": _schema("Dst", inputs=(("in", "*"),)),
        "Probe": _schema("Probe", outputs=(("IMAGE", "IMAGE"),)),
        "Foo": _schema("Foo"),
        "Bar": _schema("Bar"),
        "Test": _schema("Test"),
        "A": _schema("A"),
        "B": _schema("B"),
        "Source": _schema("Source", outputs=(("IMAGE", "IMAGE"),)),
        "Sink": _schema("Sink", inputs=(("images", "IMAGE"),)),
        "ImageScale": _schema(
            "ImageScale",
            inputs=(("image", "IMAGE"),),
            outputs=(("IMAGE", "IMAGE"),),
        ),
        "QwenEmotionNode": _schema(
            "QwenEmotionNode", outputs=(("emotion_control", "EMOTION_CONTROL"),)
        ),
        "IndexTTSEngineNode": _schema(
            "IndexTTSEngineNode", inputs=(("emotion_control", "*"),)
        ),
    }


class _DeclaredProvider:
    """Independent schema declarations with optional explicit test overrides."""

    def __init__(self, overrides=None):
        self._schemas = dict(_declared_schemas())
        if overrides is not None:
            declared = overrides.schemas() if hasattr(overrides, "schemas") else {}
            if isinstance(declared, dict):
                self._schemas.update(declared)
            getter = getattr(overrides, "get_schema", None)
            if callable(getter):
                for class_type in tuple(self._schemas):
                    actual = getter(class_type)
                    if actual is not None:
                        self._schemas[class_type] = actual

    def get_schema(self, class_type):
        return self._schemas.get(class_type)

    def schemas(self):
        return dict(self._schemas)


def _lint_fixture_delta(delta, index, schema_provider=None, **kwargs):  # type: ignore[no-redef]
    declared_provider = _DeclaredProvider(schema_provider)
    if kwargs.get("pre_workflow") is None:
        from vibecomfy.ingest.normalize import from_ui

        payload = kwargs.setdefault("pre_ui_payload", index.graph)
        kwargs["pre_workflow"] = from_ui(
            dict(payload),
            schema_provider=declared_provider,
            use_comfy_converter=False,
        )
    if kwargs.get("schema_snapshot") is None:
        from vibecomfy.comfy_nodes.agent.candidate_transaction import (
            capture_ingress_schema_snapshot,
        )

        payload = kwargs.get("pre_ui_payload", index.graph)
        kwargs["schema_snapshot"] = capture_ingress_schema_snapshot(
            schema_provider=declared_provider,
            graph=payload,
        )
    if kwargs.get("retained_authority") is None:
        from vibecomfy.ingest.snapshot import snapshot_of
        from vibecomfy.porting.edit.admit import AdmissionSnapshot

        kwargs["retained_authority"] = AdmissionSnapshot(
            workflow=snapshot_of(kwargs["pre_workflow"]),
            schema=kwargs["schema_snapshot"],
        )
    return _production_lint_delta(
        delta,
        index,
        schema_provider=declared_provider,
        **kwargs,
    )


# ── canonical uid pass-through ──────────────────────────────────────────────

def test_canonical_uid_set_node_field_passes_through() -> None:
    """A set_node_field op referencing a valid canonical uid passes unchanged."""
    idx = _index()
    # Node 2 (CLIPTextEncode) has uid "2" (its lg_id, since no explicit uid)
    target = NodeFieldTarget(scope_path="", uid="2", field_path="widgets_values")
    op = SetNodeFieldOp(op="set_node_field", target=target, value="new prompt")
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0
    assert len(result.surviving) == 1
    assert result.surviving[0] == op
    assert result.surviving[0] is not op  # report custody requires detachment


def test_canonical_uid_remove_node_passes_through() -> None:
    """A remove_node op referencing a valid canonical uid passes unchanged."""
    idx = _index()
    target = NodeTarget(scope_path="", uid="3")
    op = RemoveNodeOp(op="remove_node", target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0
    assert len(result.surviving) == 1
    assert result.surviving[0] == op
    assert result.surviving[0] is not op


def test_legacy_reorder_and_set_title_rejected_as_unknown_op() -> None:
    """reorder/set_title are not part of the grammar; lint rejects them."""
    idx = _index()
    for op in (SimpleNamespace(op="reorder"), SimpleNamespace(op="set_title")):
        result = _lint_fixture_delta([op], idx)

        assert result.passed_count == 0
        assert result.rejected_count == 1
        assert len(result.surviving) == 0
        assert result.issues[0].code == "unknown_op"


def test_canonical_uid_set_mode_passes_through() -> None:
    """A set_mode op referencing a valid canonical uid passes."""
    idx = _index()
    target = NodeTarget(scope_path="", uid="1")
    # Node 1 is mode 0; set to mode 2
    op = SetModeOp(op="set_mode", target=target, mode=2)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0


# ── LiteGraph id → canonical uid rewrite ────────────────────────────────────

def test_lg_id_rewrite_set_node_field() -> None:
    """When uid is a LiteGraph integer string, it is rewritten to the canonical uid."""
    idx = _index()
    # "2" is the LiteGraph id string; canonical uid is also "2" in flat.json
    # because no explicit vibecomfy_uid was set, but the rewrite path should
    # still resolve correctly even when they coincide.
    target = NodeFieldTarget(scope_path="", uid="2", field_path="widgets_values")
    op = SetNodeFieldOp(op="set_node_field", target=target, value="test")
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    # When lg_id == canonical uid, the op identity is preserved
    assert result.surviving[0] == op
    assert result.surviving[0] is not op


def test_lg_id_rewrite_with_custom_uid() -> None:
    """When a node has a custom vibecomfy_uid, the lg_id is rewritten."""
    raw = {
        "nodes": [
            {"id": 5, "type": "Foo", "properties": {"vibecomfy_uid": "my_custom"}, "mode": 0, "inputs": [], "outputs": []},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    # Reference by lg_id string "5"
    target = NodeTarget(scope_path="", uid="5")
    op = RemoveNodeOp(op="remove_node", target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0
    surviving = result.surviving[0]
    assert isinstance(surviving, RemoveNodeOp)
    assert surviving.target.uid == "my_custom"
    assert surviving is not op  # rewritten, so identity differs


def test_lg_id_rewrite_field_target() -> None:
    """NodeFieldTarget with lg_id is rewritten to canonical uid."""
    raw = {
        "nodes": [
            {"id": 10, "type": "Bar", "properties": {"vibecomfy_uid": "bar_node"},
             "mode": 0, "inputs": [], "outputs": [], "widgets_values": ["old"]},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    target = NodeFieldTarget(scope_path="", uid="10", field_path="widgets_values")
    op = SetNodeFieldOp(op="set_node_field", target=target, value="new")
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    surviving = result.surviving[0]
    assert isinstance(surviving, SetNodeFieldOp)
    assert surviving.target.uid == "bar_node"
    assert surviving.target.field_path == "widgets_values"
    assert surviving.value == "new"


# ── unknown target ──────────────────────────────────────────────────────────

def test_unknown_target_rejected() -> None:
    """An op referencing a non-existent uid is rejected."""
    idx = _index()
    target = NodeTarget(scope_path="", uid="nonexistent")
    op = RemoveNodeOp(op="remove_node", target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 0
    assert result.rejected_count == 1
    assert len(result.surviving) == 0
    assert len(result.issues) == 1
    assert result.issues[0].code == "unknown_target"


def test_unknown_lg_id_rejected() -> None:
    """An op referencing a non-existent LiteGraph id is rejected."""
    idx = _index()
    # flat.json only has ids 1-7
    target = NodeTarget(scope_path="", uid="999")
    op = SetModeOp(op="set_mode", target=target, mode=2)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 0
    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_target"
    assert result.issues[0].lg_id == 999


def test_unknown_target_field_op() -> None:
    """set_node_field with unknown uid is rejected."""
    idx = _index()
    target = NodeFieldTarget(scope_path="", uid="nonexistent", field_path="widgets_values")
    op = SetNodeFieldOp(op="set_node_field", target=target, value=42)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 0
    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_target"


# ── field no-op ─────────────────────────────────────────────────────────────

def test_field_noop_dropped() -> None:
    """Setting a field to its current value is a no-op and dropped."""
    raw = {
        "nodes": [
            {"id": 1, "type": "Test", "properties": {},
             "mode": 0, "inputs": [], "outputs": [],
             "widgets_values": ["hello"]},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    target = NodeFieldTarget(scope_path="", uid="1", field_path="widgets.0")
    # "hello" is the current value of widgets[0]
    op = SetNodeFieldOp(op="set_node_field", target=target, value="hello")
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 0
    assert result.dropped_count == 1
    assert result.rejected_count == 0
    assert len(result.surviving) == 0
    assert len(result.issues) == 1
    assert result.issues[0].code == "noop_field"
    assert result.issues[0].severity == "info"


def test_field_change_passes() -> None:
    """Setting a field to a different value passes."""
    raw = {
        "nodes": [
            {"id": 1, "type": "Test", "properties": {},
             "mode": 0, "inputs": [], "outputs": [],
             "widgets_values": ["hello"]},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    target = NodeFieldTarget(scope_path="", uid="1", field_path="widgets_values")
    op = SetNodeFieldOp(op="set_node_field", target=target, value="world")
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0
    assert len(result.surviving) == 1


def test_field_noop_top_level_property() -> None:
    """No-op detection works for top-level node properties like 'mode'."""
    raw = {
        "nodes": [
            {"id": 1, "type": "Test", "properties": {},
             "mode": 0, "inputs": [], "outputs": []},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    target = NodeFieldTarget(scope_path="", uid="1", field_path="mode")
    op = SetNodeFieldOp(op="set_node_field", target=target, value=0)
    result = _lint_fixture_delta([op], idx)

    assert result.dropped_count == 1
    assert result.issues[0].code == "noop_field"


# ── mode no-op ──────────────────────────────────────────────────────────────

def test_mode_noop_dropped() -> None:
    """Setting mode to the current mode is a no-op and dropped."""
    idx = _index()
    # Node 1 is mode 0
    target = NodeTarget(scope_path="", uid="1")
    op = SetModeOp(op="set_mode", target=target, mode=0)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 0
    assert result.dropped_count == 1
    assert result.rejected_count == 0
    assert len(result.surviving) == 0
    assert len(result.issues) == 1
    assert result.issues[0].code == "noop_mode"
    assert result.issues[0].severity == "info"


def test_mode_change_passes() -> None:
    """Setting mode to a different value passes."""
    idx = _index()
    target = NodeTarget(scope_path="", uid="1")
    op = SetModeOp(op="set_mode", target=target, mode=4)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0


# ── absent field ────────────────────────────────────────────────────────────

def test_absent_field_rejected() -> None:
    """Setting a field that doesn't exist on the node is rejected."""
    raw = {
        "nodes": [
            {"id": 1, "type": "Test", "properties": {},
             "mode": 0, "inputs": [], "outputs": [],
             "widgets_values": []},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    target = NodeFieldTarget(scope_path="", uid="1", field_path="nonexistent_field")
    op = SetNodeFieldOp(op="set_node_field", target=target, value=42)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 0
    assert result.dropped_count == 0
    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_field"


def test_absent_field_nonzero_widget_index() -> None:
    """A widget index beyond the widgets_values list is rejected as unknown."""
    raw = {
        "nodes": [
            {"id": 1, "type": "Test", "properties": {},
             "mode": 0, "inputs": [], "outputs": [],
             "widgets_values": ["hello"]},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    # "widgets.5" is out of range (only index 0 exists)
    target = NodeFieldTarget(scope_path="", uid="1", field_path="widgets.5")
    op = SetNodeFieldOp(op="set_node_field", target=target, value="should fail")
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_field"


def test_positional_widget_alias_uses_same_resolution_as_apply() -> None:
    raw = {
        "nodes": [
            {
                "id": 124,
                "type": "QwenEmotionNode",
                "properties": {"vibecomfy_uid": "124"},
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "widgets_values": ["model", "calm"],
            },
        ],
        "links": [],
    }
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(scope_path="", uid="124", field_path="widget_1"),
        value="dramatic",
    )

    result = _lint_fixture_delta([op], LintIndex.build(raw))

    assert result.passed_count == 1
    assert result.rejected_count == 0
    assert result.issues == ()


# ── identity rewrite pass-through (mixed delta) ─────────────────────────────

def test_identity_rewrite_mixed_delta() -> None:
    """A delta with mixed outcomes: pass, rewrite, noop, reject."""
    raw = {
        "nodes": [
            {"id": 1, "type": "A", "properties": {"vibecomfy_uid": "alpha"}, "mode": 0,
             "inputs": [], "outputs": [], "widgets_values": ["keep"]},
            {"id": 2, "type": "B", "properties": {}, "mode": 0,
             "inputs": [], "outputs": [], "widgets_values": ["old"]},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    ops: list = [
        # canonical uid pass-through
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="alpha", field_path="widgets_values"),
            value="changed",
        ),
        # lg_id rewrite needed (node "alpha" has lg_id=1)
        SetModeOp(
            op="set_mode",
            target=NodeTarget(scope_path="", uid="1"),
            mode=2,
        ),
        # field no-op (value unchanged)
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="2", field_path="widgets.0"),
            value="old",
        ),
        # unknown target
        RemoveNodeOp(
            op="remove_node",
            target=NodeTarget(scope_path="", uid="nonexistent"),
        ),
    ]

    result = _lint_fixture_delta(ops, idx)

    assert result.passed_count == 2
    assert result.dropped_count == 1
    assert result.rejected_count == 1

    assert len(result.surviving) == 2

    # First surviving op should be the set_node_field (passed through)
    s0 = result.surviving[0]
    assert isinstance(s0, SetNodeFieldOp)
    assert s0.target.uid == "alpha"

    # Second surviving op should be the set_mode (rewritten from "1" → "alpha")
    s1 = result.surviving[1]
    assert isinstance(s1, SetModeOp)
    assert s1.target.uid == "alpha"
    assert s1.mode == 2

    # Check normalizations
    assert result.normalizations[0].disposition == "passed"
    assert result.normalizations[1].disposition == "passed"
    assert result.normalizations[2].disposition == "dropped_noop"
    assert result.normalizations[3].disposition == "rejected"

    # Check issues
    issue_codes = {i.code for i in result.issues}
    assert "noop_field" in issue_codes
    assert "unknown_target" in issue_codes


# ── add_node validation ─────────────────────────────────────────────────────

def test_add_node_empty_class_type_rejected() -> None:
    """add_node with empty class_type is rejected."""
    idx = _index()
    op = AddNodeOp(op="add_node", scope_path="", class_type="  ", fields={}, inputs={})
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 0
    assert result.rejected_count == 1
    assert result.issues[0].code == "empty_class_type"


def test_add_node_valid_passes() -> None:
    """add_node with valid class_type passes."""
    idx = _index()
    op = AddNodeOp(op="add_node", scope_path="", class_type="KSampler", fields={}, inputs={})
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1


def test_add_node_unknown_scope_rejected() -> None:
    """add_node with a non-existent scope_path is rejected."""
    idx = _index()
    op = AddNodeOp(op="add_node", scope_path="nonexistent_scope", class_type="Foo", fields={}, inputs={})
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_scope"


# ── upsert_link validation ──────────────────────────────────────────────────

def test_upsert_link_valid_passes() -> None:
    """upsert_link with valid source and target endpoints that do NOT already exist passes."""
    idx = _index()
    # Node 1 output "VAE" (slot_index 2) → Node 2 input "clip" (slot 0)
    # No existing link uses this exact pair, so it should pass.
    source = LinkSourceRef(scope_path="", uid="1", output_slot="VAE")
    target = LinkTargetRef(scope_path="", uid="2", input_field="clip")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1


def test_upsert_links_from_node_added_in_same_delta_survive_lint() -> None:
    """Dependent rewires must be linted against the virtual post-add graph."""
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
    from vibecomfy.ingest.normalize import from_ui

    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "Source",
                "properties": {"vibecomfy_uid": "source"},
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}],
            },
            {
                "id": 2,
                "type": "Sink",
                "properties": {"vibecomfy_uid": "still"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
                "outputs": [],
            },
            {
                "id": 3,
                "type": "Sink",
                "properties": {"vibecomfy_uid": "video"},
                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
                "outputs": [],
            },
        ],
        "links": [],
        "last_node_id": 3,
        "last_link_id": 0,
    }

    class _StubProvider:
        def get_schema(self, class_type: str) -> NodeSchema | None:
            if class_type == "ImageScale":
                return NodeSchema(
                    class_type="ImageScale",
                    pack=None,
                    inputs={"image": InputSpec(type="IMAGE")},
                    outputs=[OutputSpec(name="IMAGE", type="IMAGE")],
                )
            return None

    ops = [
        AddNodeOp(
            op="add_node",
            scope_path="",
            class_type="ImageScale",
            fields={},
            inputs={"image": LinkSourceRef(scope_path="", uid="source", output_slot="IMAGE")},
            uid="n1",
            node_id="4",
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef(scope_path="", uid="n1", output_slot="IMAGE"),
            target=LinkTargetRef(scope_path="", uid="still", input_field="images"),
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef(scope_path="", uid="n1", output_slot="IMAGE"),
            target=LinkTargetRef(scope_path="", uid="video", input_field="images"),
        ),
    ]

    pre_workflow = from_ui(graph, use_comfy_converter=False)
    result = _lint_fixture_delta(
        ops,
        LintIndex.build(graph),
        schema_provider=_StubProvider(),
        pre_workflow=pre_workflow,
        pre_ui_payload=graph,
    )

    assert result.rejected_count == 0
    assert result.dropped_count == 0
    assert result.surviving == tuple(ops)
    assert "n1" not in pre_workflow.nodes
    assert not any(edge.from_node == "n1" for edge in pre_workflow.edges)


def test_lint_requires_retained_pre_workflow_and_frozen_snapshot() -> None:
    idx = _index()
    op = SetModeOp(op="set_mode", target=NodeTarget(scope_path="", uid="1"), mode=2)
    from vibecomfy.ingest.normalize import from_ui

    pre_workflow = from_ui(dict(idx.graph), use_comfy_converter=False)
    with pytest.raises(TypeError, match="retained_authority"):
        _production_lint_delta(
            [op], idx, pre_ui_payload=idx.graph,
            schema_snapshot=object(),
        )
    with pytest.raises(TypeError, match="retained_authority"):
        _production_lint_delta(
            [op], idx, pre_workflow=pre_workflow, pre_ui_payload=idx.graph,
        )


def test_lint_preserves_frozen_schema_payload_when_live_provider_changes() -> None:
    from vibecomfy.comfy_nodes.agent.candidate_transaction import (
        capture_ingress_schema_snapshot,
    )
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
    from vibecomfy.schema.types import schema_snapshot_to_payload
    from vibecomfy.ingest.snapshot import snapshot_of
    from vibecomfy.porting.edit.admit import AdmissionSnapshot

    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "Probe",
                "properties": {"vibecomfy_uid": "probe"},
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                "widgets_values": [0],
            }
        ],
        "links": [],
    }

    class _ChangingProvider:
        def __init__(self) -> None:
            self.calls = 0
            self.current = NodeSchema(
                "Probe", None, {}, [OutputSpec("IMAGE", "IMAGE")]
            )

        def get_schema(self, class_type: str):
            self.calls += 1
            return self.current if class_type == "Probe" else None

        def schemas(self):
            return {"Probe": self.current}

    provider = _ChangingProvider()
    snapshot = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)
    payload_before = schema_snapshot_to_payload(snapshot)
    calls_before = provider.calls
    provider.current = NodeSchema(
        "Probe", None, {"replacement": InputSpec(type="STRING")}, []
    )
    pre_workflow = from_ui(dict(graph), use_comfy_converter=False)
    op = SetModeOp(op="set_mode", target=NodeTarget(scope_path="", uid="probe"), mode=2)
    retained = AdmissionSnapshot(workflow=snapshot_of(pre_workflow), schema=snapshot)
    result = _production_lint_delta(
        [op],
        LintIndex.build(graph),
        schema_provider=provider,
        pre_workflow=pre_workflow,
        pre_ui_payload=graph,
        schema_snapshot=snapshot,
        retained_authority=retained,
    )
    assert result.rejected_count == 0
    assert result.passed_count == 1
    assert provider.calls == calls_before
    assert schema_snapshot_to_payload(snapshot) == payload_before


def test_upsert_link_unknown_source_rejected() -> None:
    """upsert_link with unknown source is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="nonexistent", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_target"


def test_upsert_link_unknown_target_rejected() -> None:
    """upsert_link with unknown target is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="1", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="nonexistent", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_target"


def test_upsert_link_lg_id_rewrite() -> None:
    """upsert_link rewrites lg_id uids in both source and target."""
    raw = {
        "nodes": [
            {"id": 10, "type": "Src", "properties": {"vibecomfy_uid": "src_node"},
             "mode": 0, "inputs": [], "outputs": [{"name": "out", "type": "*", "links": [], "slot_index": 0}]},
            {"id": 20, "type": "Dst", "properties": {"vibecomfy_uid": "dst_node"},
             "mode": 0, "inputs": [{"name": "in", "type": "*"}], "outputs": []},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    source = LinkSourceRef(scope_path="", uid="10", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="20", input_field="in")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    surviving = result.surviving[0]
    assert isinstance(surviving, UpsertLinkOp)
    assert surviving.source.uid == "src_node"
    assert surviving.target.uid == "dst_node"


# ── remove_link validation ──────────────────────────────────────────────────

def test_remove_link_by_id_valid_passes() -> None:
    """remove_link by existing link id passes."""
    idx = _index()
    # flat.json has link ids 1-9
    op = RemoveLinkOp(op="remove_link", link_id=1)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1


def test_remove_link_by_id_unknown_rejected() -> None:
    """remove_link by non-existent link id is rejected."""
    idx = _index()
    op = RemoveLinkOp(op="remove_link", link_id=9999)
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_link"


def test_remove_link_by_target_valid_passes() -> None:
    """remove_link by target endpoint passes when nodes exist."""
    idx = _index()
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = RemoveLinkOp(op="remove_link", target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1


def test_remove_link_by_target_unknown_node_rejected() -> None:
    """remove_link by target endpoint with unknown node is rejected."""
    idx = _index()
    target = LinkTargetRef(scope_path="", uid="nonexistent", input_field="model")
    op = RemoveLinkOp(op="remove_link", target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1



# ── upsert_link no-op detection ──────────────────────────────────────────────

def test_upsert_link_noop_dropped() -> None:
    """upsert_link that duplicates an existing link is dropped as a no-op."""
    idx = _index()
    # Link [1, 1, 0, 5, 0, "MODEL"] exists: node 1 output slot 0 → node 5 input "model"
    source = LinkSourceRef(scope_path="", uid="1", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 0
    assert result.dropped_count == 1
    assert result.rejected_count == 0
    assert len(result.surviving) == 0
    assert result.issues[0].code == "noop_link"
    assert result.issues[0].severity == "info"


def test_upsert_link_non_noop_rewire() -> None:
    """upsert_link to a non-existing endpoint pair passes (non-no-op rewire)."""
    idx = _index()
    # Node 2 output "CONDITIONING" (slot 0) → Node 7 input "images" (slot 0)
    # No existing link uses this pair.
    source = LinkSourceRef(scope_path="", uid="2", output_slot="CONDITIONING")
    target = LinkTargetRef(scope_path="", uid="7", input_field="images")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0


# ── upsert_link endpoint validation ──────────────────────────────────────────

def test_upsert_link_bad_output_slot() -> None:
    """upsert_link with a non-existent integer output slot is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="1", output_slot=99)
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "bad_output_slot"


def test_upsert_link_bad_output_slot_name() -> None:
    """upsert_link with a non-existent output slot name is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="1", output_slot="NONEXISTENT_OUTPUT")
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "bad_output_slot"


def test_upsert_link_accepts_schema_output_name_for_physical_output_slot() -> None:
    """Lint matches apply semantics for schema-named outputs."""
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    graph = {
        "nodes": [
            {
                "id": 124,
                "type": "QwenEmotionNode",
                "properties": {"vibecomfy_uid": "124"},
                "outputs": [{"name": "output_0", "slot_index": 0, "type": ""}],
            },
            {
                "id": 138,
                "type": "IndexTTSEngineNode",
                "properties": {"vibecomfy_uid": "138"},
                "inputs": [{"name": "emotion_control", "type": "*"}],
            },
        ],
        "links": [],
    }

    class _StubProvider:
        def get_schema(self, class_type: str) -> NodeSchema | None:
            if class_type == "QwenEmotionNode":
                return NodeSchema(
                    class_type="QwenEmotionNode",
                    pack=None,
                    inputs={},
                    outputs=[OutputSpec(name="emotion_control", type="EMOTION_CONTROL")],
                )
            if class_type == "IndexTTSEngineNode":
                return NodeSchema(
                    class_type="IndexTTSEngineNode",
                    pack=None,
                    inputs={"emotion_control": InputSpec(type="*")},
                    outputs=[],
                )
            return None

    op = UpsertLinkOp(
        op="upsert_link",
        source=LinkSourceRef(scope_path="", uid="124", output_slot="emotion_control"),
        target=LinkTargetRef(scope_path="", uid="138", input_field="emotion_control"),
    )
    result = _lint_fixture_delta([op], LintIndex.build(graph), schema_provider=_StubProvider())

    assert result.passed_count == 1
    assert result.rejected_count == 0
    assert result.issues == ()


def test_upsert_link_missing_target_input() -> None:
    """upsert_link with a target input that doesn't exist is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="1", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="5", input_field="nonexistent_input")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "missing_target_input"


# ── remove_link no-op detection ──────────────────────────────────────────────

def test_remove_link_noop_by_target() -> None:
    """remove_link by target endpoint where no link exists is a no-op."""
    idx = _index()
    # Node 5 has 4 inputs: model(0), positive(1), negative(2), latent_image(3).
    # "nonexistent_input" does not exist, so no link can match → noop.
    target = LinkTargetRef(scope_path="", uid="5", input_field="nonexistent_input")
    op = RemoveLinkOp(op="remove_link", target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.dropped_count == 1
    assert result.issues[0].code == "noop_remove_link"
    assert result.issues[0].severity == "info"


def test_remove_link_by_target_noop_empty_inputs() -> None:
    """remove_link targeting a node with no inputs is a no-op."""
    idx = _index()
    # Node 1 (CheckpointLoaderSimple) has no inputs (inputs: [])
    target = LinkTargetRef(scope_path="", uid="1", input_field="any_input")
    op = RemoveLinkOp(op="remove_link", target=target)
    result = _lint_fixture_delta([op], idx)

    # The input won't resolve and no link will be found → noop
    assert result.dropped_count == 1
    assert result.issues[0].code == "noop_remove_link"


# ── add_node schema-aware validation ─────────────────────────────────────────

def test_add_node_unknown_class_type_with_schema() -> None:
    """add_node with a class_type unknown to the schema provider is rejected."""
    from vibecomfy.schema import InputSpec, NodeSchema

    idx = _index()

    class _StubProvider:
        def get_schema(self, class_type: str) -> NodeSchema | None:
            if class_type == "KSampler":
                return NodeSchema(
                    class_type="KSampler", pack=None,
                    inputs={
                        "model": InputSpec(),
                        "positive": InputSpec(),
                        "negative": InputSpec(),
                        "latent_image": InputSpec(),
                    },
                    outputs=[],
                )
            return None

    op = AddNodeOp(op="add_node", scope_path="", class_type="UnknownClass", fields={}, inputs={})
    result = _lint_fixture_delta([op], idx, schema_provider=_StubProvider())

    assert result.passed_count == 0
    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_class_type"


def test_add_node_invalid_input_with_schema() -> None:
    """add_node with an input name not in the class schema is rejected."""
    from vibecomfy.schema import InputSpec, NodeSchema

    idx = _index()

    class _StubProvider:
        def get_schema(self, class_type: str) -> NodeSchema | None:
            if class_type == "KSampler":
                return NodeSchema(
                    class_type="KSampler", pack=None,
                    inputs={
                        "model": InputSpec(),
                        "latent_image": InputSpec(),
                    },
                    outputs=[],
                )
            return None

    op = AddNodeOp(
        op="add_node", scope_path="", class_type="KSampler",
        fields={},
        inputs={"invalid_input": LinkSourceRef(scope_path="", uid="1", output_slot=0)},
    )
    result = _lint_fixture_delta([op], idx, schema_provider=_StubProvider())

    assert result.passed_count == 0
    assert result.rejected_count == 1
    assert result.issues[0].code == "invalid_add_node_input"


def test_add_node_valid_with_schema() -> None:
    """add_node with known class_type and valid input names passes schema check."""
    from vibecomfy.schema import InputSpec, NodeSchema

    idx = _index()

    class _StubProvider:
        def get_schema(self, class_type: str) -> NodeSchema | None:
            if class_type == "KSampler":
                return NodeSchema(
                    class_type="KSampler", pack=None,
                    inputs={
                        "model": InputSpec(),
                        "positive": InputSpec(),
                        "negative": InputSpec(),
                        "latent_image": InputSpec(),
                    },
                    outputs=[],
                )
            return None

    op = AddNodeOp(
        op="add_node", scope_path="", class_type="KSampler",
        fields={},
        inputs={"model": LinkSourceRef(scope_path="", uid="1", output_slot=0)},
    )
    result = _lint_fixture_delta([op], idx, schema_provider=_StubProvider())

    assert result.passed_count == 1


# ── LiteGraph id normalization on link endpoints ─────────────────────────────

def test_upsert_link_lg_id_normalization() -> None:
    """upsert_link rewrites both source and target LiteGraph ids to canonical uids."""
    raw = {
        "nodes": [
            {
                "id": 100, "type": "Src",
                "properties": {"vibecomfy_uid": "source_canonical"},
                "mode": 0, "inputs": [],
                "outputs": [{"name": "out", "type": "*", "links": [], "slot_index": 0}],
            },
            {
                "id": 200, "type": "Dst",
                "properties": {"vibecomfy_uid": "target_canonical"},
                "mode": 0,
                "inputs": [{"name": "in", "type": "*"}],
                "outputs": [],
            },
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    source = LinkSourceRef(scope_path="", uid="100", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="200", input_field="in")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = _lint_fixture_delta([op], idx)

    assert result.passed_count == 1
    surviving = result.surviving[0]
    assert isinstance(surviving, UpsertLinkOp)
    assert surviving.source.uid == "source_canonical"
    assert surviving.target.uid == "target_canonical"
    assert surviving.source.output_slot == 0
    assert surviving.target.input_field == "in"


# ── empty delta ─────────────────────────────────────────────────────────────

def test_empty_delta() -> None:
    """An empty delta produces an empty result."""
    idx = _index()
    result = _lint_fixture_delta([], idx)

    assert result.passed_count == 0
    assert result.dropped_count == 0
    assert result.rejected_count == 0
    assert len(result.surviving) == 0
    assert len(result.issues) == 0
    assert len(result.normalizations) == 0


# ── LintResult properties ───────────────────────────────────────────────────

def test_lint_result_properties() -> None:
    """LintResult count properties are correct."""
    idx = _index()
    target1 = NodeTarget(scope_path="", uid="1")
    target2 = NodeTarget(scope_path="", uid="nonexistent")

    ops: list = [
        SetModeOp(op="set_mode", target=target1, mode=0),  # noop
        RemoveNodeOp(op="remove_node", target=target2),  # rejected
    ]

    result = _lint_fixture_delta(ops, idx)
    assert result.passed_count == 0
    assert result.dropped_count == 1
    assert result.rejected_count == 1


# ── message quality (T6) ────────────────────────────────────────────────────

def test_message_unchanged_field_assignment_is_human_readable() -> None:
    """The noop_field message uses class name, field path, and display value."""
    idx = _index("flat.json")
    # Node 2 is a CLIPTextEncode node; setting widgets_values to its current
    # value should produce a human-readable noop message.
    node = idx.node_by_uid("", "2")
    assert node is not None
    current = node.get("widgets_values")
    target = NodeFieldTarget(scope_path="", uid="2", field_path="widgets_values")
    op = SetNodeFieldOp(op="set_node_field", target=target, value=current)

    result = _lint_fixture_delta([op], idx)
    assert result.dropped_count == 1
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.code == "noop_field"
    # Message must contain the class name (CLIPTextEncode) and the field name
    assert "CLIPTextEncode" in issue.message
    assert "widgets_values" in issue.message
    # Must NOT contain raw uid, raw gate text, or from-null phrasing
    assert "'2'" not in issue.message
    assert "from null" not in issue.message.lower()
    assert "Gate" not in issue.message


def test_message_bad_output_slot_rejection_is_human_readable() -> None:
    """The bad_output_slot message uses class name and slot name, not raw uids."""
    idx = _index("flat.json")
    # Node 6 is VAEDecode; request a non-existent output slot.
    source = LinkSourceRef(scope_path="", uid="6", output_slot="NONEXISTENT")
    target_ref = LinkTargetRef(scope_path="", uid="7", input_field="images")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target_ref)

    result = _lint_fixture_delta([op], idx)
    assert result.rejected_count == 1
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.code == "bad_output_slot"
    # Message must contain the class name and slot name
    assert "VAEDecode" in issue.message
    assert "NONEXISTENT" in issue.message
    # Must NOT contain raw uid or raw gate text
    assert "'6'" not in issue.message
    assert "Gate" not in issue.message


def test_message_noop_link_is_human_readable() -> None:
    """The noop_link message uses class names and field names, not raw uids."""
    idx = _index("flat.json")
    # Find an existing link and try to upsert the same one.
    existing_links = idx.link_ids_for_scope("")
    if not existing_links:
        pytest.skip("No existing links in flat.json fixture")
    link = idx.link_by_id("", next(iter(existing_links)))
    assert link is not None
    origin_id = link.get("origin_id") if isinstance(link, dict) else link[1]
    origin_slot = link.get("origin_slot") if isinstance(link, dict) else link[2]
    target_id = link.get("target_id") if isinstance(link, dict) else link[3]
    target_slot = link.get("target_slot") if isinstance(link, dict) else link[4]

    source_uid = idx.uid_for_lg_id("", origin_id)
    target_uid = idx.uid_for_lg_id("", target_id)
    assert source_uid is not None and target_uid is not None

    # Resolve slot names
    source_meta = idx.node_meta_for("", source_uid)
    target_meta = idx.node_meta_for("", target_uid)
    assert source_meta is not None and target_meta is not None
    # Find output name for origin_slot
    source_slot_name = None
    for name, slot_idx in source_meta.output_slots.items():
        if slot_idx == origin_slot:
            source_slot_name = name
            break
    if source_slot_name is None:
        source_slot_name = origin_slot

    # Find input name for target_slot
    target_input_name = None
    if 0 <= target_slot < len(target_meta.input_names):
        target_input_name = target_meta.input_names[target_slot]

    if target_input_name is None:
        pytest.skip("Could not resolve target input name")

    source = LinkSourceRef(scope_path="", uid=source_uid, output_slot=source_slot_name)
    target_ref = LinkTargetRef(scope_path="", uid=target_uid, input_field=target_input_name)
    op = UpsertLinkOp(op="upsert_link", source=source, target=target_ref)

    result = _lint_fixture_delta([op], idx)
    assert result.dropped_count == 1
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.code == "noop_link"
    # Message must contain class names (not raw uids) and field name
    assert "already exists" in issue.message.lower()
    assert target_input_name in issue.message
    # Must NOT contain raw uid-like '4[' pattern or gate text
    assert "'" not in issue.message  # no raw uid quoted
    assert "Gate" not in issue.message


# ── T20 canonical transition/evidence contract ─────────────────────────────

def _transition_outcomes(result: LintResult) -> tuple[str, ...]:
    """Keep assertions independent of the report's diagnostic payload shape."""
    return tuple(item.outcome for item in result.transitions)


def test_transition_report_is_detached_and_nested_values_are_immutable() -> None:
    idx = _index()
    value = {"nested": ["before"]}
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(scope_path="", uid="2", field_path="widgets_values.0"),
        value=value,
    )
    result = _lint_fixture_delta([op], idx)

    assert _transition_outcomes(result) == ("staged",)
    report = result.transitions[0]
    assert report.occurrence == 0
    assert report.submitted is not op
    value["nested"].append("mutated-after-report")
    assert "mutated-after-report" not in repr(report.submitted)
    with pytest.raises((AttributeError, TypeError)):
        report.outcome = "rejected"
    with pytest.raises((TypeError, AttributeError)):
        report.submitted.value["nested"].append("alias")


def test_repeated_writes_are_reported_by_occurrence_and_not_field_key() -> None:
    idx = _index()
    target = NodeFieldTarget(scope_path="", uid="2", field_path="widgets_values.0")
    ops = [
        SetNodeFieldOp(op="set_node_field", target=target, value="first"),
        SetNodeFieldOp(op="set_node_field", target=target, value="first"),
        SetNodeFieldOp(op="set_node_field", target=target, value="second"),
    ]
    result = _lint_fixture_delta(ops, idx)

    assert [n.disposition for n in result.normalizations] == [
        "passed", "dropped_noop", "passed"
    ]
    assert _transition_outcomes(result) == ("staged", "noop", "staged")
    assert [item.occurrence for item in result.transitions] == [0, 1, 2]
    assert len(result.surviving) == 2


def test_remove_link_id_then_repeat_uses_current_canonical_edge() -> None:
    idx = _index()
    first = RemoveLinkOp(op="remove_link", link_id=1)
    second = RemoveLinkOp(op="remove_link", link_id=1)
    result = _lint_fixture_delta([first, second], idx)

    assert [n.disposition for n in result.normalizations] == [
        "passed", "dropped_noop"
    ]
    assert _transition_outcomes(result) == ("staged", "noop")
    assert len(result.surviving) == 1
    lowered = result.transitions[0].lowered
    assert lowered and all(getattr(item, "target", None) is not None for item in lowered)


@pytest.mark.parametrize("field_path", ["widgets.0", "widgets_values.0", "widget_0"])
def test_widget_aliases_lower_to_the_same_canonical_carrier(field_path: str) -> None:
    graph = {
        "nodes": [{
            "id": 1,
            "type": "Probe",
            "properties": {"vibecomfy_uid": "probe"},
            "widgets_values": ["old"],
            "inputs": [],
            "outputs": [],
        }],
        "links": [],
    }
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(scope_path="", uid="probe", field_path=field_path),
        value="new",
    )
    result = _lint_fixture_delta([op], LintIndex.build(graph))
    assert result.passed_count == 1
    assert _transition_outcomes(result) == ("staged",)
    assert len(result.transitions[0].lowered) == 1
    lowered = result.transitions[0].lowered[0]
    assert isinstance(lowered, SetNodeFieldOp)
    assert lowered.target == NodeFieldTarget(
        scope_path="", uid="probe", field_path="widget_0"
    )
    assert lowered.value == "new"


def test_aggregate_widget_replacement_is_atomic_and_scalar_is_rejected_at_apply() -> None:
    graph = {
        "nodes": [{
            "id": 1,
            "type": "Probe",
            "properties": {"vibecomfy_uid": "probe"},
            "widgets_values": ["old", 1],
            "inputs": [],
            "outputs": [],
        }],
        "links": [],
    }
    target = NodeFieldTarget(scope_path="", uid="probe", field_path="widgets_values")
    valid = SetNodeFieldOp(op="set_node_field", target=target, value=["new", 2])
    scalar = SetNodeFieldOp(op="set_node_field", target=target, value="not-an-aggregate")
    result = _lint_fixture_delta([valid, scalar], LintIndex.build(graph))

    # Both are presentation-normalized; only the canonical evaluator can
    # establish whether the aggregate is an exact complete replacement.
    assert [n.disposition for n in result.normalizations] == ["passed", "passed"]
    assert _transition_outcomes(result) == ("staged", "rejected")
    lowered = result.transitions[0].lowered
    assert [(op.target.field_path, op.value) for op in lowered] == [
        ("widget_0", "new"),
        ("widget_1", 2),
    ]
    assert result.transitions[0].normalized.value == ("new", 2)

    from vibecomfy.comfy_nodes.agent.candidate_transaction import (
        capture_ingress_schema_snapshot,
    )
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit._interpret import _evaluate_operation
    from vibecomfy.schema import FrozenSchemaSnapshotProvider

    provider = _DeclaredProvider()
    snapshot = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)
    frozen = FrozenSchemaSnapshotProvider(snapshot)
    workflow = from_ui(dict(graph), schema_provider=frozen, use_comfy_converter=False)
    evaluation = _evaluate_operation(workflow, valid, schema_provider=frozen)
    assert evaluation.outcome == "staged"
    assert evaluation.workflow != workflow
    assert evaluation.workflow.nodes["1"].widgets == {
        "widget_0": "new",
        "widget_1": 2,
    }
    assert evaluation.presentation_ui is not None
    assert evaluation.presentation_ui["nodes"][0]["widgets_values"] == ["new", 2]
    assert result.transitions[1].diagnostics
    # Preview is analysis only: one rejected occurrence makes the whole
    # transaction ineligible, even when an earlier occurrence staged.
    assert not result.apply_eligible


@pytest.mark.parametrize(
    ("replacement", "changed_field"),
    [
        (["old", 2], "widget_1"),
        (["new", 1], "widget_0"),
    ],
)
def test_aggregate_replacement_tolerates_unchanged_constituents(
    replacement: list[object], changed_field: str,
) -> None:
    graph = {
        "nodes": [{
            "id": 1,
            "type": "Probe",
            "properties": {"vibecomfy_uid": "probe"},
            "widgets_values": ["old", 1],
            "inputs": [],
            "outputs": [],
        }],
        "links": [],
    }
    target = NodeFieldTarget(scope_path="", uid="probe", field_path="widgets_values")
    result = _lint_fixture_delta(
        [SetNodeFieldOp(op="set_node_field", target=target, value=replacement)],
        LintIndex.build(graph),
    )

    assert result.normalizations[0].disposition == "passed"
    assert _transition_outcomes(result) == ("staged",)
    assert [op.target.field_path for op in result.transitions[0].lowered] == [
        "widget_0", "widget_1"
    ]
    assert changed_field in {
        op.target.field_path
        for op in result.transitions[0].lowered
        if op.value != ("old" if op.target.field_path == "widget_0" else 1)
    }

    from vibecomfy.comfy_nodes.agent.candidate_transaction import (
        capture_ingress_schema_snapshot,
    )
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit._interpret import _evaluate_operation
    from vibecomfy.schema import FrozenSchemaSnapshotProvider

    provider = _DeclaredProvider()
    snapshot = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)
    frozen = FrozenSchemaSnapshotProvider(snapshot)
    workflow = from_ui(dict(graph), schema_provider=frozen, use_comfy_converter=False)
    evaluation = _evaluate_operation(
        workflow,
        SetNodeFieldOp(op="set_node_field", target=target, value=replacement),
        schema_provider=frozen,
    )
    assert evaluation.outcome == "staged"
    assert evaluation.workflow != workflow
    assert evaluation.workflow.nodes["1"].widgets == {
        "widget_0": replacement[0],
        "widget_1": replacement[1],
    }
    assert evaluation.presentation_ui is not None
    assert evaluation.presentation_ui["nodes"][0]["widgets_values"] == replacement


def test_mapping_aggregate_replacement_uses_frozen_roster_and_exact_values() -> None:
    graph = {
        "nodes": [{
            "id": 1,
            "type": "Probe",
            "properties": {"vibecomfy_uid": "probe"},
            "widgets_values": ["old", 1],
            "inputs": [],
            "outputs": [],
        }],
        "links": [],
    }
    target = NodeFieldTarget(scope_path="", uid="probe", field_path="widgets_values")
    replacement = {"widget_0": "new", "widget_1": 2}
    result = _lint_fixture_delta(
        [SetNodeFieldOp(op="set_node_field", target=target, value=replacement)],
        LintIndex.build(graph),
    )

    assert result.normalizations[0].disposition == "passed"
    assert _transition_outcomes(result) == ("staged",)
    assert [
        (op.target.field_path, op.value)
        for op in result.transitions[0].lowered
    ] == [("widget_0", "new"), ("widget_1", 2)]

    from vibecomfy.comfy_nodes.agent.candidate_transaction import (
        capture_ingress_schema_snapshot,
    )
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit._interpret import _evaluate_operation
    from vibecomfy.schema import FrozenSchemaSnapshotProvider

    provider = _DeclaredProvider()
    snapshot = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)
    frozen = FrozenSchemaSnapshotProvider(snapshot)
    workflow = from_ui(dict(graph), schema_provider=frozen, use_comfy_converter=False)
    evaluation = _evaluate_operation(
        workflow,
        SetNodeFieldOp(op="set_node_field", target=target, value=replacement),
        schema_provider=frozen,
    )
    assert evaluation.outcome == "staged"
    assert evaluation.workflow != workflow
    assert evaluation.workflow.nodes["1"].widgets == replacement
    assert evaluation.presentation_ui is not None
    assert evaluation.presentation_ui["nodes"][0]["widgets_values"] == ["new", 2]


def test_scalar_one_slot_aggregate_is_lint_passed_but_application_rejected() -> None:
    graph = {
        "nodes": [{
            "id": 1,
            "type": "Probe",
            "properties": {"vibecomfy_uid": "probe"},
            "widgets_values": ["old"],
            "inputs": [],
            "outputs": [],
        }],
        "links": [],
    }
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(scope_path="", uid="probe", field_path="widgets_values"),
        value="scalar-must-not-coerce",
    )
    result = _lint_fixture_delta([op], LintIndex.build(graph))

    assert result.normalizations[0].disposition == "passed"
    assert _transition_outcomes(result) == ("rejected",)
    assert result.transitions[0].diagnostics
    assert not result.apply_eligible


def test_mode_field_lowers_to_set_mode_and_repeated_mode_is_noop() -> None:
    idx = _index()
    target = NodeFieldTarget(scope_path="", uid="1", field_path="mode")
    op = SetNodeFieldOp(op="set_node_field", target=target, value=4)
    repeat = SetNodeFieldOp(op="set_node_field", target=target, value=4)
    result = _lint_fixture_delta([op, repeat], idx)

    assert [n.disposition for n in result.normalizations] == ["passed", "dropped_noop"]
    assert _transition_outcomes(result) == ("staged", "noop")
    assert any(getattr(item, "op", None) == "set_mode" for item in result.transitions[0].lowered)


def test_lint_pass_can_have_explicit_unresolved_application_rejection() -> None:
    graph = {
        "nodes": [{
            "id": 1,
            "type": "Probe",
            "properties": {"vibecomfy_uid": "probe"},
            "widgets_values": ["old"],
            "inputs": [],
            "outputs": [],
        }],
        "links": [],
    }
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(scope_path="", uid="probe", field_path="unresolved_widget"),
        value="new",
    )
    result = _lint_fixture_delta([op], LintIndex.build(graph))

    assert result.passed_count == 1
    assert result.normalizations[0].issue is not None
    assert result.normalizations[0].issue.code == "unknown_field"
    assert _transition_outcomes(result) == ("rejected",)
    assert result.surviving == (op,)
    assert not result.apply_eligible


def test_incompatible_rewire_survives_presentation_lint_but_rejects_application() -> None:
    graph = {
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple", "inputs": [],
             "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images", "type": "IMAGE"}],
             "outputs": []},
        ],
        "links": [],
    }
    op = UpsertLinkOp(
        op="upsert_link",
        source=LinkSourceRef(scope_path="", uid="1", output_slot="MODEL"),
        target=LinkTargetRef(scope_path="", uid="2", input_field="images"),
    )
    result = _lint_fixture_delta([op], LintIndex.build(graph))

    assert result.passed_count == 1
    assert _transition_outcomes(result) == ("rejected",)
    assert result.surviving == (op,)
    assert not result.apply_eligible


def test_rejected_add_does_not_authorize_later_dependency() -> None:
    idx = _index()
    rejected_add = AddNodeOp(
        op="add_node", scope_path="", class_type="UnknownClass",
        uid="future", node_id="99", fields={}, inputs={},
    )
    dependent = SetModeOp(
        op="set_mode", target=NodeTarget(scope_path="", uid="future"), mode=2
    )
    result = _lint_fixture_delta([rejected_add, dependent], idx)

    assert result.normalizations[0].disposition == "rejected"
    assert result.normalizations[1].disposition == "rejected"
    assert _transition_outcomes(result) == ("rejected", "rejected")


def test_authority_digest_and_presentation_mismatch_fail_closed() -> None:
    from dataclasses import replace
    from vibecomfy.comfy_nodes.agent.candidate_transaction import capture_ingress_schema_snapshot
    from vibecomfy.ingest.normalize import from_ui

    graph = _fixture("flat.json")
    provider = _DeclaredProvider()
    snapshot = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)
    workflow = from_ui(dict(graph), schema_provider=provider, use_comfy_converter=False)
    op = SetModeOp(op="set_mode", target=NodeTarget(scope_path="", uid="1"), mode=2)
    from vibecomfy.ingest.snapshot import snapshot_of
    from vibecomfy.porting.edit.admit import AdmissionSnapshot
    retained = AdmissionSnapshot(workflow=snapshot_of(workflow), schema=snapshot)

    corrupt = replace(snapshot, content_digest="0" * len(snapshot.content_digest))
    with pytest.raises((ValueError, TypeError)):
        _production_lint_delta(
            [op], LintIndex.build(graph), schema_provider=provider,
            pre_workflow=workflow, pre_ui_payload=graph, schema_snapshot=corrupt,
            retained_authority=retained,
        )
    changed_ui = dict(graph)
    changed_ui["nodes"] = list(graph["nodes"])
    changed_ui["nodes"][0] = dict(changed_ui["nodes"][0], mode=7)
    with pytest.raises((ValueError, TypeError)):
        _production_lint_delta(
            [op], LintIndex.build(changed_ui), schema_provider=provider,
            pre_workflow=workflow, pre_ui_payload=changed_ui, schema_snapshot=snapshot,
            retained_authority=retained,
        )


def test_compact_roster_skips_linked_socket_before_widget_slot() -> None:
    from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node

    node = {
        "class_type": "VoxelToMeshBasic",
        "widgets_values": [0.6],
        "metadata": {
            "input_aliases": ["voxel"],
            "_ui": {"inputs": [{"name": "voxel", "type": "VOXEL", "link": 7}]},
        },
    }
    resolution = compact_widget_names_for_node(node, "VoxelToMeshBasic")

    assert resolution.names == ("widget_0",)


def test_link_id_lowering_uses_canonical_uid_and_current_edge_hint() -> None:
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "Src",
                "properties": {"vibecomfy_uid": "u1"},
                "inputs": [],
                "outputs": [{"name": "out", "type": "*", "slot_index": 0}],
            },
            {
                "id": 2,
                "type": "Dst",
                "properties": {"vibecomfy_uid": "u2"},
                "inputs": [{"name": "in", "type": "*", "link": 7}],
                "outputs": [],
            },
        ],
        "links": [[7, 1, 0, 2, 0, "*"]],
    }
    result = _lint_fixture_delta(
        [RemoveLinkOp(op="remove_link", link_id=7)], LintIndex.build(graph)
    )

    assert _transition_outcomes(result) == ("staged",)
    lowered = result.transitions[0].lowered
    assert len(lowered) == 1
    lowered_target = getattr(lowered[0], "target", None)
    assert lowered_target is not None
    assert lowered_target.uid == "u2"
    assert lowered_target.input_field == "in"


def test_ambient_lookup_false_is_rejected_not_rewritten() -> None:
    from dataclasses import replace
    from vibecomfy.comfy_nodes.agent.candidate_transaction import capture_ingress_schema_snapshot
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.schema import SchemaSnapshotError

    graph = _fixture("flat.json")
    provider = _DeclaredProvider()
    snapshot = capture_ingress_schema_snapshot(schema_provider=provider, graph=graph)
    workflow = from_ui(dict(graph), schema_provider=provider, use_comfy_converter=False)
    malformed = replace(snapshot, ambient_lookup_forbidden=False)
    op = SetModeOp(op="set_mode", target=NodeTarget(scope_path="", uid="1"), mode=2)
    from vibecomfy.ingest.snapshot import snapshot_of
    from vibecomfy.porting.edit.admit import AdmissionSnapshot
    retained = AdmissionSnapshot(workflow=snapshot_of(workflow), schema=snapshot)

    with pytest.raises(SchemaSnapshotError, match="ambient"):
        _production_lint_delta(
            [op], LintIndex.build(graph), schema_provider=provider,
            pre_workflow=workflow, pre_ui_payload=graph, schema_snapshot=malformed,
            retained_authority=retained,
        )


def test_live_provider_without_snapshot_fails_closed() -> None:
    from vibecomfy.ingest.normalize import from_ui

    graph = _fixture("flat.json")
    provider = _DeclaredProvider()
    workflow = from_ui(dict(graph), schema_provider=provider, use_comfy_converter=False)
    op = SetModeOp(op="set_mode", target=NodeTarget(scope_path="", uid="1"), mode=2)

    with pytest.raises(TypeError, match="retained_authority"):
        _production_lint_delta(
            [op], LintIndex.build(graph), schema_provider=provider,
            pre_workflow=workflow, pre_ui_payload=graph,
        )


def test_forged_presentation_widget_value_rejects_against_retained_workflow() -> None:
    from vibecomfy.comfy_nodes.agent.candidate_transaction import capture_ingress_schema_snapshot
    from vibecomfy.ingest.normalize import from_ui

    original = _fixture("flat.json")
    provider = _DeclaredProvider()
    snapshot = capture_ingress_schema_snapshot(schema_provider=provider, graph=original)
    workflow = from_ui(dict(original), schema_provider=provider, use_comfy_converter=False)
    from vibecomfy.ingest.snapshot import snapshot_of
    from vibecomfy.porting.edit.admit import AdmissionSnapshot
    retained = AdmissionSnapshot(workflow=snapshot_of(workflow), schema=snapshot)
    forged = dict(original)
    forged["nodes"] = list(original["nodes"])
    forged["nodes"][1] = dict(forged["nodes"][1], widgets_values=["forged"])
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(scope_path="", uid="2", field_path="widgets_values.0"),
        value="forged",
    )

    with pytest.raises(ValueError, match="presentation"):
        _production_lint_delta(
            [op], LintIndex.build(forged), schema_provider=provider,
            pre_workflow=workflow, pre_ui_payload=forged, schema_snapshot=snapshot,
            retained_authority=retained,
        )
