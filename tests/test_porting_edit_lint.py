"""Tests for vibecomfy.porting.edit_lint — lint_delta() behaviour.

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
- reorder uid resolution
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.porting.edit.lint import (
    LintIndex,
    LintResult,
    lint_delta,
)
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    ReorderOp,
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


# ── canonical uid pass-through ──────────────────────────────────────────────

def test_canonical_uid_set_node_field_passes_through() -> None:
    """A set_node_field op referencing a valid canonical uid passes unchanged."""
    idx = _index()
    # Node 2 (CLIPTextEncode) has uid "2" (its lg_id, since no explicit uid)
    target = NodeFieldTarget(scope_path="", uid="2", field_path="widgets_values")
    op = SetNodeFieldOp(op="set_node_field", target=target, value="new prompt")
    result = lint_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0
    assert len(result.surviving) == 1
    assert result.surviving[0] is op  # identity preserved when no rewrite needed


def test_canonical_uid_remove_node_passes_through() -> None:
    """A remove_node op referencing a valid canonical uid passes unchanged."""
    idx = _index()
    target = NodeTarget(scope_path="", uid="3")
    op = RemoveNodeOp(op="remove_node", target=target)
    result = lint_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0
    assert len(result.surviving) == 1
    assert result.surviving[0] is op


def test_canonical_uid_reorder_passes_through() -> None:
    """A reorder op referencing a valid canonical uid passes unchanged."""
    idx = _index()
    target = NodeTarget(scope_path="", uid="5")
    op = ReorderOp(op="reorder", target=target, axis="widgets", order=("a", "b"))
    result = lint_delta([op], idx)

    assert result.passed_count == 1
    assert result.dropped_count == 0
    assert result.rejected_count == 0
    assert len(result.surviving) == 1
    assert result.surviving[0] is op


def test_canonical_uid_set_mode_passes_through() -> None:
    """A set_mode op referencing a valid canonical uid passes."""
    idx = _index()
    target = NodeTarget(scope_path="", uid="1")
    # Node 1 is mode 0; set to mode 2
    op = SetModeOp(op="set_mode", target=target, mode=2)
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

    assert result.passed_count == 1
    # When lg_id == canonical uid, the op identity is preserved
    assert result.surviving[0] is op


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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

    assert result.passed_count == 0
    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_target"
    assert result.issues[0].lg_id == 999


def test_unknown_target_field_op() -> None:
    """set_node_field with unknown uid is rejected."""
    idx = _index()
    target = NodeFieldTarget(scope_path="", uid="nonexistent", field_path="widgets_values")
    op = SetNodeFieldOp(op="set_node_field", target=target, value=42)
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

    assert result.dropped_count == 1
    assert result.issues[0].code == "noop_field"


# ── mode no-op ──────────────────────────────────────────────────────────────

def test_mode_noop_dropped() -> None:
    """Setting mode to the current mode is a no-op and dropped."""
    idx = _index()
    # Node 1 is mode 0
    target = NodeTarget(scope_path="", uid="1")
    op = SetModeOp(op="set_mode", target=target, mode=0)
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_field"


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

    result = lint_delta(ops, idx)

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
    result = lint_delta([op], idx)

    assert result.passed_count == 0
    assert result.rejected_count == 1
    assert result.issues[0].code == "empty_class_type"


def test_add_node_valid_passes() -> None:
    """add_node with valid class_type passes."""
    idx = _index()
    op = AddNodeOp(op="add_node", scope_path="", class_type="KSampler", fields={}, inputs={})
    result = lint_delta([op], idx)

    assert result.passed_count == 1


def test_add_node_unknown_scope_rejected() -> None:
    """add_node with a non-existent scope_path is rejected."""
    idx = _index()
    op = AddNodeOp(op="add_node", scope_path="nonexistent_scope", class_type="Foo", fields={}, inputs={})
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

    assert result.passed_count == 1


def test_upsert_link_unknown_source_rejected() -> None:
    """upsert_link with unknown source is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="nonexistent", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = lint_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_target"


def test_upsert_link_unknown_target_rejected() -> None:
    """upsert_link with unknown target is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="1", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="nonexistent", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

    assert result.passed_count == 1


def test_remove_link_by_id_unknown_rejected() -> None:
    """remove_link by non-existent link id is rejected."""
    idx = _index()
    op = RemoveLinkOp(op="remove_link", link_id=9999)
    result = lint_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_link"


def test_remove_link_by_target_valid_passes() -> None:
    """remove_link by target endpoint passes when nodes exist."""
    idx = _index()
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = RemoveLinkOp(op="remove_link", target=target)
    result = lint_delta([op], idx)

    assert result.passed_count == 1


def test_remove_link_by_target_unknown_node_rejected() -> None:
    """remove_link by target endpoint with unknown node is rejected."""
    idx = _index()
    target = LinkTargetRef(scope_path="", uid="nonexistent", input_field="model")
    op = RemoveLinkOp(op="remove_link", target=target)
    result = lint_delta([op], idx)

    assert result.rejected_count == 1


# ── reorder validation ──────────────────────────────────────────────────────

def test_reorder_unknown_target_rejected() -> None:
    """reorder with unknown target is rejected."""
    idx = _index()
    target = NodeTarget(scope_path="", uid="nonexistent")
    op = ReorderOp(op="reorder", target=target, axis="widgets", order=("a",))
    result = lint_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "unknown_target"


def test_reorder_lg_id_rewrite() -> None:
    """reorder rewrites lg_id to canonical uid."""
    raw = {
        "nodes": [
            {"id": 7, "type": "Z", "properties": {"vibecomfy_uid": "zeta"}, "mode": 0,
             "inputs": [], "outputs": []},
        ],
        "links": [],
    }
    idx = LintIndex.build(raw)

    target = NodeTarget(scope_path="", uid="7")
    op = ReorderOp(op="reorder", target=target, axis="slots", order=("x", "y"))
    result = lint_delta([op], idx)

    assert result.passed_count == 1
    surviving = result.surviving[0]
    assert isinstance(surviving, ReorderOp)
    assert surviving.target.uid == "zeta"
    assert surviving.axis == "slots"


# ── upsert_link no-op detection ──────────────────────────────────────────────

def test_upsert_link_noop_dropped() -> None:
    """upsert_link that duplicates an existing link is dropped as a no-op."""
    idx = _index()
    # Link [1, 1, 0, 5, 0, "MODEL"] exists: node 1 output slot 0 → node 5 input "model"
    source = LinkSourceRef(scope_path="", uid="1", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "bad_output_slot"


def test_upsert_link_bad_output_slot_name() -> None:
    """upsert_link with a non-existent output slot name is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="1", output_slot="NONEXISTENT_OUTPUT")
    target = LinkTargetRef(scope_path="", uid="5", input_field="model")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = lint_delta([op], idx)

    assert result.rejected_count == 1
    assert result.issues[0].code == "bad_output_slot"


def test_upsert_link_missing_target_input() -> None:
    """upsert_link with a target input that doesn't exist is rejected."""
    idx = _index()
    source = LinkSourceRef(scope_path="", uid="1", output_slot=0)
    target = LinkTargetRef(scope_path="", uid="5", input_field="nonexistent_input")
    op = UpsertLinkOp(op="upsert_link", source=source, target=target)
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx)

    assert result.dropped_count == 1
    assert result.issues[0].code == "noop_remove_link"
    assert result.issues[0].severity == "info"


def test_remove_link_by_target_noop_empty_inputs() -> None:
    """remove_link targeting a node with no inputs is a no-op."""
    idx = _index()
    # Node 1 (CheckpointLoaderSimple) has no inputs (inputs: [])
    target = LinkTargetRef(scope_path="", uid="1", input_field="any_input")
    op = RemoveLinkOp(op="remove_link", target=target)
    result = lint_delta([op], idx)

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
    result = lint_delta([op], idx, schema_provider=_StubProvider())

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
    result = lint_delta([op], idx, schema_provider=_StubProvider())

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
    result = lint_delta([op], idx, schema_provider=_StubProvider())

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
    result = lint_delta([op], idx)

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
    result = lint_delta([], idx)

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

    result = lint_delta(ops, idx)
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

    result = lint_delta([op], idx)
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

    result = lint_delta([op], idx)
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

    result = lint_delta([op], idx)
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
