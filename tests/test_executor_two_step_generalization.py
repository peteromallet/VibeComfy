"""Codex DOES-NOT-GENERALIZE regression suite.

Each priority below reproduces an out-of-fixture failure the original fixes
missed, then pins the generalization so it cannot regress:

1. multi-widget named-field replay (two_step_session._replay_named_field_op)
2. add_node named widget fields survive replay (schema-less → widgets_values)
3. link-op attribution marks every node the wire touched (no ghost link refs)
4. edit_batch builds against the SEQUENTIAL IR state (distinct uids; add+link)
5. malformed arg-shape errors never consume the replacement window
6. apply_ops gate rejections normalize to ``verification_failed``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.executor.edit_tools import EditToolRuntime, build_edit_ops, validate_edit_tool_args
from vibecomfy.executor.two_step_session import _apply_delta_ops
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec


# ── schema fixtures ──────────────────────────────────────────────────────────


class _LawProvider:
    def get_schema(self, class_type: str) -> Any:
        schemas = {
            "LawNodeA": NodeSchema("LawNodeA", "law", {}, [OutputSpec("IMAGE", "IMAGE")]),
            "LawNodeB": NodeSchema("LawNodeB", "law", {}, [OutputSpec("IMAGE", "IMAGE")]),
            "LawNodeC": NodeSchema(
                "LawNodeC",
                "law",
                {"image": InputSpec("IMAGE"), "prompt": InputSpec("STRING")},
                [],
            ),
            "LawNodeD": NodeSchema("LawNodeD", "law", {"value": InputSpec("FLOAT")}, []),
            "LoopNode": NodeSchema(
                "LoopNode",
                "law",
                {"image": InputSpec("IMAGE")},
                [OutputSpec("IMAGE", "IMAGE")],
            ),
        }
        return schemas.get(class_type)


def _law_ui() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "1", "type": "LawNodeA", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}], "widgets_values": []},
            {"id": "2", "type": "LawNodeB", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2]}], "widgets_values": []},
            {"id": "3", "type": "LawNodeC", "inputs": [{"name": "image", "type": "IMAGE", "link": 1}], "outputs": [], "widgets_values": ["before"]},
        ],
        "links": [
            [1, "1", 0, "3", 0, "IMAGE"],
            [2, "2", 0, "3", 0, "IMAGE"],
        ],
    }


def _law_session() -> EditSession:
    return EditSession(dict(_law_ui()), schema_provider=_LawProvider())


def _widgets_values(graph: dict[str, Any], node_id: str) -> list[Any]:
    for node in graph.get("nodes") or ():
        if isinstance(node, dict) and str(node.get("id")) == node_id:
            return list(node.get("widgets_values") or [])
    raise AssertionError(f"node {node_id!r} not in graph")


def _ghost_link_refs(graph: dict[str, Any]) -> list[str]:
    """Return any node slot that references a link id absent from ``links``."""
    link_ids = set()
    for link in graph.get("links") or ():
        if isinstance(link, (list, tuple)) and link and isinstance(link[0], int):
            link_ids.add(link[0])
        elif isinstance(link, dict) and isinstance(link.get("id"), int):
            link_ids.add(link["id"])
    ghosts: list[str] = []
    for node in graph.get("nodes") or ():
        if not isinstance(node, dict):
            continue
        for inp in node.get("inputs") or ():
            if isinstance(inp, dict) and isinstance(inp.get("link"), int) and inp["link"] not in link_ids:
                ghosts.append(f"{node.get('id')}.inputs.link={inp['link']}")
        for out in node.get("outputs") or ():
            if not isinstance(out, dict):
                continue
            for ref in out.get("links") or ():
                if isinstance(ref, int) and ref not in link_ids:
                    ghosts.append(f"{node.get('id')}.outputs.links={ref}")
    return ghosts


# ── Priority 1: multi-widget named-field replay ──────────────────────────────


def test_multi_widget_named_field_replay_survives() -> None:
    """A named-field edit on a 2-widget node must replay positionally.

    ``LoraLoaderModelOnly`` has committed widget order ``[lora_name,
    strength_model]``; the live path records the SCHEMA name ``lora_name``.
    Schema-less replay must map it to ``widget_0`` — not an unknown input
    channel that emission then drops.
    """
    base = {
        "nodes": [
            {"id": "1", "type": "LoraLoaderModelOnly", "inputs": [], "outputs": [], "widgets_values": ["before", 1.0]},
        ],
        "links": [],
    }
    op = {"op": "set_node_field", "target": ["", "1", "lora_name"], "value": "after"}
    replayed = _apply_delta_ops(base, (op,))
    assert _widgets_values(replayed, "1") == ["after", 1.0]


def test_multi_widget_replay_does_not_disturb_other_slot() -> None:
    base = {
        "nodes": [
            {"id": "1", "type": "LoraLoaderModelOnly", "inputs": [], "outputs": [], "widgets_values": ["before", 1.0]},
        ],
        "links": [],
    }
    op = {"op": "set_node_field", "target": ["", "1", "strength_model"], "value": 2.5}
    replayed = _apply_delta_ops(base, (op,))
    assert _widgets_values(replayed, "1") == ["before", 2.5]


# ── Priority 2: add_node named fields survive replay ─────────────────────────


def test_add_node_named_fields_replay_widgets_values() -> None:
    """Named ``add_node`` fields must replay as positional ``widgets_values``."""
    base = {"nodes": [], "links": []}
    op = {
        "op": "add_node",
        "scope_path": "",
        "uid": "n1",
        "node_id": "1",
        "class_type": "KSampler",
        "fields": {"steps": 30, "cfg": 7.5, "seed": 1},
        "inputs": {},
    }
    replayed = _apply_delta_ops(base, (op,))
    assert _widgets_values(replayed, "1") == [30, 7.5, 1]


def test_add_node_named_fields_order_preserved() -> None:
    base = {"nodes": [], "links": []}
    op = {
        "op": "add_node",
        "scope_path": "",
        "uid": "n1",
        "node_id": "1",
        "class_type": "KSampler",
        "fields": {"seed": 11, "steps": 22, "cfg": 33},
        "inputs": {},
    }
    replayed = _apply_delta_ops(base, (op,))
    assert _widgets_values(replayed, "1") == [11, 22, 33]


# ── Priority 3: link attribution (no ghost refs) ─────────────────────────────


def _source_target_ui() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "1", "type": "LawNodeA", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}], "widgets_values": []},
            {"id": "3", "type": "LawNodeC", "inputs": [{"name": "image", "type": "IMAGE", "link": 1}], "outputs": [], "widgets_values": ["before"]},
        ],
        "links": [[1, "1", 0, "3", 0, "IMAGE"]],
    }


def test_remove_node_source_clears_target_link() -> None:
    """Removing the SOURCE node must clear the surviving target's input link."""
    base = _source_target_ui()
    replayed = _apply_delta_ops(base, ({"op": "remove_node", "target": ["", "1"]},))
    assert _ghost_link_refs(replayed) == []
    target = next(n for n in replayed["nodes"] if str(n.get("id")) == "3")
    for inp in target.get("inputs") or ():
        assert inp.get("link") is None, "target input still references a removed link"


def test_remove_link_clears_both_endpoints() -> None:
    base = _source_target_ui()
    replayed = _apply_delta_ops(base, ({"op": "remove_link", "to": ["", "3", "image"]},))
    assert _ghost_link_refs(replayed) == []


def test_upsert_link_displaces_old_source_cleanly() -> None:
    base = {
        "nodes": [
            {"id": "1", "type": "LawNodeA", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}], "widgets_values": []},
            {"id": "2", "type": "LawNodeB", "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []}], "widgets_values": []},
            {"id": "3", "type": "LawNodeC", "inputs": [{"name": "image", "type": "IMAGE", "link": 1}], "outputs": [], "widgets_values": ["before"]},
        ],
        "links": [[1, "1", 0, "3", 0, "IMAGE"]],
    }
    replayed = _apply_delta_ops(
        base,
        ({"op": "upsert_link", "from": ["", "2", "IMAGE"], "to": ["", "3", "image"]},),
    )
    assert _ghost_link_refs(replayed) == []


def test_remove_node_reingest_same_quotient() -> None:
    """The replayed graph re-ingests without resurrecting removed links."""
    from tests.test_ir_laws import pi_edit  # noqa: F401

    base = _source_target_ui()
    replayed = _apply_delta_ops(base, ({"op": "remove_node", "target": ["", "1"]},))
    assert _ghost_link_refs(replayed) == []
    # Re-ingest must not raise and must not re-create the removed edge.
    from vibecomfy.ingest.normalize import from_ui

    workflow = from_ui(replayed, use_comfy_converter=False)
    assert len(workflow.edges) == 0


# ── Priority 4: edit_batch sequential pre-state ──────────────────────────────


def test_edit_batch_two_add_nodes_mint_distinct_uids() -> None:
    session = _law_session()
    ops = build_edit_ops(
        session,
        "edit_batch",
        {"ops": [
            {"op": "add_node", "class_type": "LawNodeD", "widget_values": {"value": 0.25}},
            {"op": "add_node", "class_type": "LawNodeD", "widget_values": {"value": 0.75}},
        ]},
    )
    uids = [getattr(op, "uid") for op in ops]
    node_ids = [getattr(op, "node_id") for op in ops]
    assert len(set(uids)) == 2, f"distinct uids required, got {uids}"
    assert len(set(node_ids)) == 2, f"distinct node ids required, got {node_ids}"


def test_edit_batch_add_then_link_resolves() -> None:
    """add-then-link in ONE batch resolves the newly added node."""
    session = _law_session()
    ops = build_edit_ops(
        session,
        "edit_batch",
        {"ops": [
            {"op": "add_node", "class_type": "LawNodeD", "widget_values": {"value": 0.25}},
            {"op": "upsert_link", "source": "lawnoded", "source_output": "value", "target": "lawnodec", "target_input": "image"},
        ]},
    )
    assert [getattr(op, "op") for op in ops] == ["add_node", "upsert_link"]
    # The link resolves the freshly minted uid, not an unknown target.
    link_op = ops[1]
    assert link_op.source.uid == getattr(ops[0], "uid")


# ── Priority 5: malformed arg-shape errors don't consume the replacement ─────


def test_widget_N_field_does_not_consume_replacement() -> None:
    runtime = EditToolRuntime(edit_session=_law_session())
    first = runtime.dispatch("edit_node", {"target": "lawnodec", "field": "widget_2", "value": "x"})
    assert first.ok is False
    assert first.reason == "invalid_arguments"
    assert first.replacement_allowed is True, "malformed arg must NOT consume the replacement"
    second = runtime.dispatch("edit_node", {"target": "lawnodec", "field": "prompt", "value": "ok"})
    assert second.ok is True
    assert second.delta_id == "d1"


def test_blank_target_does_not_consume_replacement() -> None:
    runtime = EditToolRuntime(edit_session=_law_session())
    first = runtime.dispatch("edit_node", {"target": "", "field": "prompt", "value": "x"})
    assert first.ok is False
    assert first.reason == "invalid_arguments"
    assert first.replacement_allowed is True
    second = runtime.dispatch("edit_node", {"target": "lawnodec", "field": "prompt", "value": "ok"})
    assert second.ok is True


# ── Priority 6: gate reasons normalize to verification_failed ────────────────


def _loop_ui() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "1", "type": "LoopNode", "inputs": [{"name": "image", "type": "IMAGE"}], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []}], "widgets_values": []},
        ],
        "links": [],
    }


def test_self_loop_rejection_normalizes_to_verification_failed() -> None:
    """A newly created self-loop rejects with the advertised code, not ``new_self_loop``."""
    session = EditSession(dict(_loop_ui()), schema_provider=_LawProvider())
    from vibecomfy.porting.edit.ops import LinkSourceRef, LinkTargetRef, UpsertLinkOp

    op = UpsertLinkOp(
        op="upsert_link",
        source=LinkSourceRef(scope_path="", uid="1", output_slot="IMAGE"),
        target=LinkTargetRef(scope_path="", uid="1", input_field="image"),
    )
    result = session.apply_ops((op,))
    assert result.ok is False
    assert result.reason == "verification_failed", result.reason
    joined = " | ".join(str(d.message) for d in result.diagnostics if hasattr(d, "message"))
    assert "new_self_loop" in joined, joined
