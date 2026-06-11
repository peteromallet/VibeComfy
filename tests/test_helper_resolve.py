"""Tests for vibecomfy.porting.helper_resolve — the fixed-point helper resolver.

Covers:
  - Phase A: GetNode broadcast-pair rewriting and hard errors on unresolved names
  - Phase B: Reroute/PrimitiveNode passthrough chain following and dangling errors
  - Phase C: value-primitive literal folding, named single-consumer register_input,
             named multi-consumer and unnamed fold-only, type coercion
  - Fixed-point: Reroute(Reroute(GetNode)) and SetNode→Primitive chains
  - Edge and node cleanup: only surviving-endpoint edges kept, all helper nodes deleted
  - Return type: ResolveDiagnostics
  - Runexx oracle regression: nodes 1862/1865/1871/1919/1929 from
    workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json
"""

from __future__ import annotations

import pytest

from vibecomfy.errors import ConversionParityError
from vibecomfy.porting.helper_resolve import ResolveDiagnostics, resolve_helpers
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.workflow import RawWidgetPayload, VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ─── Minimal workflow builder ────────────────────────────────────────────────


def _wf(*node_specs: tuple, edges: list[tuple] | None = None) -> VibeWorkflow:
    """Build a minimal VibeWorkflow for testing.

    node_specs: (node_id, class_type, kwargs_dict)
      Keys prefixed with "w_" go to node.widgets; all others go to node.inputs.

    edges: list of (from_node, from_output, to_node, to_input) tuples.
    """
    wf = VibeWorkflow(id="test", source=WorkflowSource(id="test", path=None))
    for nid, class_type, kw in node_specs:
        inputs: dict = {}
        widgets: dict = {}
        for k, v in kw.items():
            if k.startswith("w_"):
                widgets[k[2:]] = v
            else:
                inputs[k] = v
        wf.nodes[str(nid)] = VibeNode(
            id=str(nid), class_type=class_type, inputs=inputs, widgets=widgets
        )
    for from_node, from_output, to_node, to_input in (edges or []):
        wf.edges.append(
            VibeEdge(str(from_node), str(from_output), str(to_node), str(to_input))
        )
    return wf


# ─── Phase A — Broadcast pair resolution ────────────────────────────────────


class TestPhaseA:
    def test_get_node_edge_rewritten_to_upstream_source(self) -> None:
        """GetNode outbound edge is rewritten to the SetNode's upstream source."""
        # Source(0) → SetNode(1, 'sig') ← edge from 0
        # GetNode(2, 'sig') → Consumer(3)
        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "SetNode", {"widget_0": "sig"}),
            ("2", "GetNode", {"widget_0": "sig"}),
            ("3", "ConsumerNode", {}),
            edges=[
                ("0", "0", "1", "DATA"),
                ("2", "0", "3", "inp"),
            ],
        )
        resolve_helpers(wf, {})
        # Consumer edge now comes from SourceNode, not GetNode
        consumer_edges = [e for e in wf.edges if e.to_node == "3"]
        assert len(consumer_edges) == 1
        assert consumer_edges[0].from_node == "0"

    def test_set_node_and_get_node_deleted_after_resolve(self) -> None:
        """Both SetNode and GetNode are removed from workflow.nodes after resolution."""
        wf = _wf(
            ("10", "CheckpointLoaderSimple", {}),
            ("11", "SetNode", {"widget_0": "model"}),
            ("12", "GetNode", {"widget_0": "model"}),
            ("13", "KSampler", {}),
            edges=[
                ("10", "0", "11", "MODEL"),
                ("12", "0", "13", "model"),
            ],
        )
        resolve_helpers(wf, {})
        assert "11" not in wf.nodes
        assert "12" not in wf.nodes
        assert "10" in wf.nodes
        assert "13" in wf.nodes

    def test_unmatched_get_node_broadcast_raises(self) -> None:
        """GetNode referencing a broadcast name with no matching SetNode → ConversionParityError."""
        wf = _wf(
            ("1", "GetNode", {"widget_0": "ghost_broadcast"}),
            ("2", "ConsumerNode", {}),
            edges=[("1", "0", "2", "x")],
        )
        with pytest.raises(ConversionParityError, match="GetNode"):
            resolve_helpers(wf, {})

    def test_multiple_get_nodes_same_broadcast(self) -> None:
        """Multiple GetNodes sharing one broadcast name are all rewritten."""
        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "SetNode", {"widget_0": "shared"}),
            ("2", "GetNode", {"widget_0": "shared"}),
            ("3", "GetNode", {"widget_0": "shared"}),
            ("4", "ConsA", {}),
            ("5", "ConsB", {}),
            edges=[
                ("0", "0", "1", "DATA"),
                ("2", "0", "4", "in1"),
                ("3", "0", "5", "in2"),
            ],
        )
        resolve_helpers(wf, {})
        edges_4 = [e for e in wf.edges if e.to_node == "4"]
        edges_5 = [e for e in wf.edges if e.to_node == "5"]
        assert len(edges_4) == 1 and edges_4[0].from_node == "0"
        assert len(edges_5) == 1 and edges_5[0].from_node == "0"


# ─── Phase B — Passthrough resolution ───────────────────────────────────────


class TestPhaseB:
    def test_single_reroute_rewritten(self) -> None:
        """Single Reroute edge is rewritten to the terminal non-passthrough source."""
        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "Reroute", {}),
            ("2", "ConsumerNode", {}),
            edges=[
                ("0", "0", "1", ""),
                ("1", "0", "2", "v"),
            ],
        )
        resolve_helpers(wf, {})
        assert "1" not in wf.nodes
        edges = [e for e in wf.edges if e.to_node == "2"]
        assert len(edges) == 1
        assert edges[0].from_node == "0"

    def test_reroute_chain_followed_transitively(self) -> None:
        """Reroute → Reroute → Consumer chain is fully followed."""
        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "Reroute", {}),
            ("2", "Reroute", {}),
            ("3", "ConsumerNode", {}),
            edges=[
                ("0", "0", "1", ""),
                ("1", "0", "2", ""),
                ("2", "0", "3", "val"),
            ],
        )
        resolve_helpers(wf, {})
        assert "1" not in wf.nodes
        assert "2" not in wf.nodes
        edges = [e for e in wf.edges if e.to_node == "3"]
        assert len(edges) == 1
        assert edges[0].from_node == "0"

    def test_primitive_node_passthrough_rewritten(self) -> None:
        """PrimitiveNode (passthrough) is resolved to its inbound source."""
        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "PrimitiveNode", {}),
            ("2", "ConsumerNode", {}),
            edges=[
                ("0", "0", "1", ""),
                ("1", "0", "2", "field"),
            ],
        )
        resolve_helpers(wf, {})
        assert "1" not in wf.nodes
        edges = [e for e in wf.edges if e.to_node == "2"]
        assert len(edges) == 1
        assert edges[0].from_node == "0"

    def test_reroute_fan_out_all_consumers_rewritten(self) -> None:
        """A Reroute with multiple outbound edges rewrites all of them."""
        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "Reroute", {}),
            ("2", "ConsA", {}),
            ("3", "ConsB", {}),
            edges=[
                ("0", "0", "1", ""),
                ("1", "0", "2", "a"),
                ("1", "0", "3", "b"),
            ],
        )
        resolve_helpers(wf, {})
        assert "1" not in wf.nodes
        assert any(e.from_node == "0" and e.to_node == "2" for e in wf.edges)
        assert any(e.from_node == "0" and e.to_node == "3" for e in wf.edges)

    def test_dangling_reroute_raises(self) -> None:
        """Reroute with no inbound source edge → ConversionParityError."""
        wf = _wf(
            ("1", "Reroute", {}),
            ("2", "ConsumerNode", {}),
            edges=[("1", "0", "2", "x")],
        )
        with pytest.raises(ConversionParityError, match="dangling passthrough"):
            resolve_helpers(wf, {})

    def test_dangling_primitive_node_raises(self) -> None:
        """PrimitiveNode with no inbound source edge → literal folded into consumer."""
        wf = _wf(
            ("1", "PrimitiveNode", {}),
            ("2", "ConsumerNode", {}),
            edges=[("1", "0", "2", "y")],
        )
        resolve_helpers(wf, {})
        # After resolution: PrimitiveNode is deleted, its value is folded
        # into ConsumerNode's inputs, and the edge is removed
        assert "1" not in wf.nodes
        assert "2" in wf.nodes


# ─── Phase C — Value primitive literal folding ───────────────────────────────


class TestPhaseC:
    def test_unnamed_primitive_folds_literal(self) -> None:
        """PrimitiveInt with no broadcast name folds literal directly into consumer."""
        wf = _wf(
            ("0", "PrimitiveInt", {"w_widget_0": 42}),
            ("1", "KSampler", {}),
            edges=[("0", "0", "1", "seed")],
        )
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)
        assert not ri
        assert "seed" not in wf.inputs
        assert wf.nodes["1"].inputs["seed"] == 42
        assert "0" not in wf.nodes

    def test_named_single_consumer_registers_public_input(self) -> None:
        """Named PrimitiveBoolean with exactly one consumer registers as public input."""
        # PrimitiveBoolean(0, False) → SetNode(1, 't2v_mode')
        # GetNode(2, 't2v_mode') → Consumer(3, 'enabled')
        wf = _wf(
            ("0", "PrimitiveBoolean", {"w_widget_0": False}),
            ("1", "SetNode", {"widget_0": "t2v_mode"}),
            ("2", "GetNode", {"widget_0": "t2v_mode"}),
            ("3", "LazySwitchKJ", {}),
            edges=[
                ("0", "0", "1", "BOOLEAN"),
                ("2", "0", "3", "enabled"),
            ],
        )
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)
        assert "t2v_mode" in ri
        assert ri["t2v_mode"] == ("3", "enabled")
        assert "t2v_mode" in wf.inputs
        assert wf.inputs["t2v_mode"].value is False
        assert wf.inputs["t2v_mode"].default is False
        assert wf.nodes["3"].inputs["enabled"] is False

    def test_named_multi_consumer_folds_no_register_input(self) -> None:
        """Named primitive with >1 consumer folds literal per consumer, no register_input."""
        # PrimitiveFloat(0, 24.0) → SetNode(1, 'fps')
        # GetNode(2, 'fps') → Consumer(3).a  AND  Consumer(4).b
        wf = _wf(
            ("0", "PrimitiveFloat", {"w_widget_0": 24.0}),
            ("1", "SetNode", {"widget_0": "fps"}),
            ("2", "GetNode", {"widget_0": "fps"}),
            ("3", "SimpleCalcA", {}),
            ("4", "SimpleCalcB", {}),
            edges=[
                ("0", "0", "1", "FLOAT"),
                ("2", "0", "3", "a"),
                ("2", "0", "4", "b"),
            ],
        )
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)
        # fps NOT in registered_inputs (multi-consumer)
        assert "fps" not in ri
        assert "fps" not in wf.inputs
        # Literal folded into both consumers
        assert wf.nodes["3"].inputs["a"] == pytest.approx(24.0)
        assert wf.nodes["4"].inputs["b"] == pytest.approx(24.0)
        assert "0" not in wf.nodes

    def test_primitive_float_folds_into_linked_widget_value_slot(self) -> None:
        """PrimitiveFloat feeding a widget-as-link input updates the literal widget slot."""
        wf = _wf(
            ("0", "PrimitiveFloat", {"w_widget_0": 7.5}),
            ("1", "KSampler", {}),
            edges=[("0", "0", "1", "cfg")],
        )
        sampler = wf.nodes["1"]
        sampler.inputs.update(
            {
                "seed": 5,
                "steps": 20,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            }
        )
        sampler.metadata["_ui"] = {
            "widgets_values": [5, "fixed", 20, 1.0, "euler", "normal", 1.0],
            "inputs": [{"name": "cfg", "link": 1, "widget": {"name": "cfg"}}],
        }
        sampler.raw_widgets = RawWidgetPayload(
            values=[5, "fixed", 20, 1.0, "euler", "normal", 1.0],
            shape="list",
            source="ui.widgets_values",
            has_dict_rows=False,
            length=7,
        )

        resolve_helpers(wf, {})

        assert "0" not in wf.nodes
        assert wf.edges == []
        assert wf.nodes["1"].inputs["cfg"] == pytest.approx(7.5)
        assert wf.nodes["1"].metadata["_ui"]["widgets_values"][3] == pytest.approx(7.5)
        assert wf.nodes["1"].raw_widgets is not None
        assert wf.nodes["1"].raw_widgets.values[3] == pytest.approx(7.5)
        emitted = next(node for node in emit_ui_json(wf)["nodes"] if node["id"] == 1)
        assert emitted["widgets_values"][3] == pytest.approx(7.5)

    def test_primitive_boolean_coercion(self) -> None:
        """PrimitiveBoolean coerces value to Python bool."""
        for raw, expected in [(True, True), (False, False), (1, True), (0, False)]:
            wf = _wf(
                ("0", "PrimitiveBoolean", {"w_widget_0": raw}),
                ("1", "Node", {}),
                edges=[("0", "0", "1", "flag")],
            )
            resolve_helpers(wf, {})
            assert wf.nodes["1"].inputs["flag"] is expected

    def test_primitive_int_coercion(self) -> None:
        """PrimitiveInt coerces value to int."""
        wf = _wf(
            ("0", "PrimitiveInt", {"w_widget_0": 3.9}),
            ("1", "Node", {}),
            edges=[("0", "0", "1", "steps")],
        )
        resolve_helpers(wf, {})
        assert wf.nodes["1"].inputs["steps"] == 3
        assert isinstance(wf.nodes["1"].inputs["steps"], int)

    def test_primitive_float_coercion(self) -> None:
        """PrimitiveFloat coerces value to float."""
        wf = _wf(
            ("0", "PrimitiveFloat", {"w_widget_0": 7}),
            ("1", "Node", {}),
            edges=[("0", "0", "1", "cfg")],
        )
        resolve_helpers(wf, {})
        assert wf.nodes["1"].inputs["cfg"] == pytest.approx(7.0)
        assert isinstance(wf.nodes["1"].inputs["cfg"], float)

    def test_primitive_string_coercion(self) -> None:
        """PrimitiveString coerces value to str."""
        wf = _wf(
            ("0", "PrimitiveString", {"w_widget_0": 42}),
            ("1", "Node", {}),
            edges=[("0", "0", "1", "text")],
        )
        resolve_helpers(wf, {})
        assert wf.nodes["1"].inputs["text"] == "42"

    def test_primitive_string_multiline_coercion(self) -> None:
        """PrimitiveStringMultiline coerces value to str."""
        wf = _wf(
            ("0", "PrimitiveStringMultiline", {"w_widget_0": "hello\nworld"}),
            ("1", "Node", {}),
            edges=[("0", "0", "1", "prompt")],
        )
        resolve_helpers(wf, {})
        assert wf.nodes["1"].inputs["prompt"] == "hello\nworld"

    def test_primitive_reads_named_value_input_field(self) -> None:
        """PrimitiveFloat reads inputs['value'] (post alias resolution form) before widget_0."""
        # inputs['value'] takes precedence over widgets['widget_0']
        wf = _wf(
            ("0", "PrimitiveFloat", {"value": 3.14, "w_widget_0": 0.0}),
            ("1", "Node", {}),
            edges=[("0", "0", "1", "v")],
        )
        resolve_helpers(wf, {})
        assert wf.nodes["1"].inputs["v"] == pytest.approx(3.14)

    def test_primitive_none_value_uses_class_default(self) -> None:
        """PrimitiveInt with no value field defaults to 0."""
        wf = _wf(
            ("0", "PrimitiveInt", {}),
            ("1", "Node", {}),
            edges=[("0", "0", "1", "seed")],
        )
        resolve_helpers(wf, {})
        assert wf.nodes["1"].inputs["seed"] == 0


# ─── Fixed-point behavior ────────────────────────────────────────────────────


class TestFixedPoint:
    def test_reroute_of_get_node_resolved_in_two_phases(self) -> None:
        """GetNode → Reroute chain resolved: Phase A rewrites GetNode, Phase B rewrites Reroute."""
        # Source(0) → SetNode(1, 'data')
        # GetNode(2, 'data') → Reroute(3) → Consumer(4)
        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "SetNode", {"widget_0": "data"}),
            ("2", "GetNode", {"widget_0": "data"}),
            ("3", "Reroute", {}),
            ("4", "ConsumerNode", {}),
            edges=[
                ("0", "0", "1", "MODEL"),
                ("2", "0", "3", ""),
                ("3", "0", "4", "inp"),
            ],
        )
        resolve_helpers(wf, {})
        for nid in ("1", "2", "3"):
            assert nid not in wf.nodes
        edges = [e for e in wf.edges if e.to_node == "4"]
        assert len(edges) == 1
        assert edges[0].from_node == "0"

    def test_reroute_reroute_get_node_three_phase_chain(self) -> None:
        """Reroute(Reroute(GetNode)) fully resolved across fixed-point iterations."""
        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "SetNode", {"widget_0": "deep"}),
            ("2", "GetNode", {"widget_0": "deep"}),
            ("3", "Reroute", {}),
            ("4", "Reroute", {}),
            ("5", "ConsumerNode", {}),
            edges=[
                ("0", "0", "1", "MODEL"),
                ("2", "0", "3", ""),
                ("3", "0", "4", ""),
                ("4", "0", "5", "input"),
            ],
        )
        resolve_helpers(wf, {})
        for nid in ("1", "2", "3", "4"):
            assert nid not in wf.nodes
        edges = [e for e in wf.edges if e.to_node == "5"]
        assert len(edges) == 1
        assert edges[0].from_node == "0"

    def test_set_node_to_primitive_chain(self) -> None:
        """PrimitiveFloat → SetNode → GetNode → Consumer resolved end-to-end."""
        wf = _wf(
            ("0", "PrimitiveFloat", {"w_widget_0": 7.5}),
            ("1", "SetNode", {"widget_0": "rate"}),
            ("2", "GetNode", {"widget_0": "rate"}),
            ("3", "ConsumerNode", {}),
            edges=[
                ("0", "0", "1", "FLOAT"),
                ("2", "0", "3", "x"),
            ],
        )
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)
        assert "rate" in ri
        assert ri["rate"] == ("3", "x")
        assert wf.nodes["3"].inputs["x"] == pytest.approx(7.5)
        assert wf.inputs["rate"].value == pytest.approx(7.5)

    def test_primitive_via_reroute_to_consumer(self) -> None:
        """PrimitiveInt → SetNode → GetNode → Reroute → Consumer resolved in fixed-point."""
        wf = _wf(
            ("0", "PrimitiveInt", {"w_widget_0": 20}),
            ("1", "SetNode", {"widget_0": "steps"}),
            ("2", "GetNode", {"widget_0": "steps"}),
            ("3", "Reroute", {}),
            ("4", "KSampler", {}),
            edges=[
                ("0", "0", "1", "INT"),
                ("2", "0", "3", ""),
                ("3", "0", "4", "steps"),
            ],
        )
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)
        # Only one real consumer (4), but it's reached via Reroute which is also a helper.
        # After Phase A: 2→3 becomes 0→3; after Phase B: 0→3→4 becomes 0→4.
        # After Phase C: PrimitiveInt(0) has 1 real consumer (4); bname='steps' → register_input.
        assert "steps" in ri
        assert ri["steps"] == ("4", "steps")
        assert wf.nodes["4"].inputs["steps"] == 20


# ─── Determinism ─────────────────────────────────────────────────────────────\n\n\nclass TestDeterminism:\n    def test_resolve_same_fixture_twice_identical_ir(self) -> None:\n        \"\"\"Resolving the same fixture twice produces identical IR (nodes, edges, inputs).\"\"\"\n        def _build() -> VibeWorkflow:\n            return _wf(\n                (\"0\", \"SourceNode\", {}),\n                (\"1\", \"SetNode\", {\"widget_0\": \"data\"}),\n                (\"2\", \"GetNode\", {\"widget_0\": \"data\"}),\n                (\"3\", \"Reroute\", {}),\n                (\"4\", \"ConsumerNode\", {}),\n                edges=[\n                    (\"0\", \"0\", \"1\", \"DATA\"),\n                    (\"2\", \"0\", \"3\", \"\"),\n                    (\"3\", \"0\", \"4\", \"inp\"),\n                ],\n            )\n\n        ri1: dict[str, tuple[str, str]] = {}\n        wf1 = _build()\n        resolve_helpers(wf1, ri1)\n\n        ri2: dict[str, tuple[str, str]] = {}\n        wf2 = _build()\n        resolve_helpers(wf2, ri2)\n\n        # Registered inputs identical.\n        assert ri1 == ri2\n\n        # Same surviving node IDs.\n        assert set(wf1.nodes.keys()) == set(wf2.nodes.keys())\n\n        # Same node content (class_type, inputs, widgets).\n        for nid in wf1.nodes:\n            n1 = wf1.nodes[nid]\n            n2 = wf2.nodes[nid]\n            assert n1.class_type == n2.class_type\n            assert n1.inputs == n2.inputs\n            assert n1.widgets == n2.widgets\n\n        # Same edge set (order-independent comparison).\n        def _edge_key(e: VibeEdge) -> tuple[str, str, str, str]:\n            return (e.from_node, e.from_output, e.to_node, e.to_input)\n\n        edges1 = sorted(wf1.edges, key=_edge_key)\n        edges2 = sorted(wf2.edges, key=_edge_key)\n        assert [_edge_key(e) for e in edges1] == [_edge_key(e) for e in edges2]\n\n        # Same workflow inputs.\n        assert set(wf1.inputs.keys()) == set(wf2.inputs.keys())\n\n    def test_oracle_resolve_twice_full_ir_identical(self) -> None:\n        \"\"\"Two independent resolves of the runexx oracle produce identical full IR.\"\"\"\n        from tests.test_helper_resolve import TestRunexxOracle\n\n        ri1: dict[str, tuple[str, str]] = {}\n        wf1 = TestRunexxOracle()._build_oracle_wf()\n        resolve_helpers(wf1, ri1)\n\n        ri2: dict[str, tuple[str, str]] = {}\n        wf2 = TestRunexxOracle()._build_oracle_wf()\n        resolve_helpers(wf2, ri2)\n\n        # Registered inputs identical.\n        assert ri1 == ri2\n\n        # Same surviving node IDs.\n        assert set(wf1.nodes.keys()) == set(wf2.nodes.keys())\n\n        # Same node content.\n        for nid in wf1.nodes:\n            n1 = wf1.nodes[nid]\n            n2 = wf2.nodes[nid]\n            assert n1.class_type == n2.class_type\n            assert n1.inputs == n2.inputs\n            assert n1.widgets == n2.widgets\n\n        # Same edge set.\n        def _edge_key(e: VibeEdge) -> tuple[str, str, str, str]:\n            return (e.from_node, e.from_output, e.to_node, e.to_input)\n\n        edges1 = sorted(wf1.edges, key=_edge_key)\n        edges2 = sorted(wf2.edges, key=_edge_key)\n        assert [_edge_key(e) for e in edges1] == [_edge_key(e) for e in edges2]\n\n        # Same workflow inputs.\n        assert set(wf1.inputs.keys()) == set(wf2.inputs.keys())\n\n\n# ─── Edge and node cleanup ───────────────────────────────────────────────────


class TestCleanup:
    def test_edges_between_non_helper_nodes_kept(self) -> None:
        """Edges between non-helper nodes are not removed."""
        wf = _wf(
            ("1", "NodeA", {}),
            ("2", "NodeB", {}),
            edges=[("1", "0", "2", "inp")],
        )
        resolve_helpers(wf, {})
        assert len(wf.edges) == 1
        assert wf.edges[0].from_node == "1"
        assert wf.edges[0].to_node == "2"

    def test_helper_nodes_not_in_resolvable_set_are_untouched(self) -> None:
        """Note/MarkdownNote (UI_ONLY, not RESOLVABLE) are not modified by the resolver."""
        wf = _wf(
            ("1", "Note", {"text": "hello"}),
            ("2", "KSampler", {}),
        )
        resolve_helpers(wf, {})
        # Note is NOT in RESOLVABLE_HELPER_CLASS_TYPES, resolver ignores it
        assert "1" in wf.nodes

    def test_all_resolvable_helpers_deleted_after_resolution(self) -> None:
        """No RESOLVABLE_HELPER_CLASS_TYPES nodes remain after a successful resolve."""
        from vibecomfy._workflow_helpers import RESOLVABLE_HELPER_CLASS_TYPES

        wf = _wf(
            ("0", "SourceNode", {}),
            ("1", "SetNode", {"widget_0": "x"}),
            ("2", "GetNode", {"widget_0": "x"}),
            ("3", "Reroute", {}),
            ("4", "ConsumerNode", {}),
            edges=[
                ("0", "0", "1", "DATA"),
                ("2", "0", "3", ""),
                ("3", "0", "4", "v"),
            ],
        )
        resolve_helpers(wf, {})
        for nid, node in wf.nodes.items():
            assert node.class_type not in RESOLVABLE_HELPER_CLASS_TYPES, (
                f"Helper node {nid!r} ({node.class_type}) was not removed"
            )


# ─── Return value ────────────────────────────────────────────────────────────


class TestReturnValue:
    def test_returns_resolve_diagnostics(self) -> None:
        """resolve_helpers returns a ResolveDiagnostics instance."""
        wf = VibeWorkflow(id="empty", source=WorkflowSource(id="empty", path=None))
        result = resolve_helpers(wf, {})
        assert isinstance(result, ResolveDiagnostics)
        assert isinstance(result.diagnostics, list)

    def test_empty_workflow_returns_empty_diagnostics(self) -> None:
        """An empty workflow produces no diagnostics."""
        wf = VibeWorkflow(id="empty", source=WorkflowSource(id="empty", path=None))
        result = resolve_helpers(wf, {})
        assert result.diagnostics == []

    def test_workflow_without_helpers_returns_empty_diagnostics(self) -> None:
        """A workflow with no helper nodes produces no diagnostics."""
        wf = _wf(
            ("1", "CheckpointLoaderSimple", {}),
            ("2", "KSampler", {}),
            edges=[("1", "0", "2", "model")],
        )
        result = resolve_helpers(wf, {})
        assert result.diagnostics == []


# ─── Runexx oracle regression ────────────────────────────────────────────────


class TestRunexxOracle:
    """Regression fixtures from the runexx oracle (T1 audit):
    workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json.

    Oracle nodes verified in T1:
      1862 — PrimitiveBoolean(False) → SetNode(1861, 't2v_mode')
      1929 — PrimitiveBoolean(True)  → SetNode(1930, 'enhance_prompt')
      1586 — PrimitiveFloat(24.0)    → SetNode(1577, 'fps') → GetNode(1871) → KJ(1651).a
      1897 — SimpleCalculatorKJ      → SetNode(1918, 'frames_seconds') → GetNode(1919) → two consumers
      1904 — AudioEnhancementNode    → SetNode(1758, 'audio_tts') → GetNode(1784) → Reroute(1865) → [1893, 1920]
    """

    def _build_oracle_wf(self) -> VibeWorkflow:
        """Construct a minimal VibeWorkflow that reproduces the oracle chains."""
        wf = VibeWorkflow(
            id="test/runexx_oracle",
            source=WorkflowSource(id="test/runexx_oracle", path=None),
        )

        # ── Oracle 1862: PrimitiveBoolean(False) → SetNode(1861, 't2v_mode') ──
        # Consumer: GetNode(9003, 't2v_mode') → LazySwitchKJ(9001).t2v_mode
        wf.nodes["1862"] = VibeNode("1862", "PrimitiveBoolean", widgets={"widget_0": False})
        wf.nodes["1861"] = VibeNode("1861", "SetNode", widgets={"widget_0": "t2v_mode"})
        wf.nodes["9003"] = VibeNode("9003", "GetNode", widgets={"widget_0": "t2v_mode"})
        wf.nodes["9001"] = VibeNode("9001", "LazySwitchKJ")
        wf.edges.append(VibeEdge("1862", "0", "1861", "BOOLEAN"))
        wf.edges.append(VibeEdge("9003", "0", "9001", "t2v_mode"))

        # ── Oracle 1929: PrimitiveBoolean(True) → SetNode(1930, 'enhance_prompt') ──
        # Consumer: GetNode(9004, 'enhance_prompt') → LTXNode(9002).enhance_prompt
        wf.nodes["1929"] = VibeNode("1929", "PrimitiveBoolean", widgets={"widget_0": True})
        wf.nodes["1930"] = VibeNode("1930", "SetNode", widgets={"widget_0": "enhance_prompt"})
        wf.nodes["9004"] = VibeNode("9004", "GetNode", widgets={"widget_0": "enhance_prompt"})
        wf.nodes["9002"] = VibeNode("9002", "LTXVideoModelLoader")
        wf.edges.append(VibeEdge("1929", "0", "1930", "BOOLEAN"))
        wf.edges.append(VibeEdge("9004", "0", "9002", "enhance_prompt"))

        # ── Oracle 1586/1577/1871/1651: PrimitiveFloat(24.0) → SetNode('fps') → GetNode → KJ ──
        wf.nodes["1586"] = VibeNode("1586", "PrimitiveFloat", widgets={"widget_0": 24.0})
        wf.nodes["1577"] = VibeNode("1577", "SetNode", widgets={"widget_0": "fps"})
        wf.nodes["1871"] = VibeNode("1871", "GetNode", widgets={"widget_0": "fps"})
        wf.nodes["1651"] = VibeNode("1651", "SimpleCalculatorKJ")
        wf.edges.append(VibeEdge("1586", "0", "1577", "FLOAT"))
        wf.edges.append(VibeEdge("1871", "0", "1651", "a"))

        # ── Oracle 1897/1918/1919/1900/1899: non-primitive SetNode → GetNode → two consumers ──
        # (frames_seconds: SimpleCalculatorKJ → SetNode → GetNode → [LazySwitchKJ, SimpleCalcKJ])
        wf.nodes["1897"] = VibeNode("1897", "SimpleCalculatorKJ")
        wf.nodes["1918"] = VibeNode("1918", "SetNode", widgets={"widget_0": "frames_seconds"})
        wf.nodes["1919"] = VibeNode("1919", "GetNode", widgets={"widget_0": "frames_seconds"})
        wf.nodes["1900"] = VibeNode("1900", "LazySwitchKJ")
        wf.nodes["1899"] = VibeNode("1899", "SimpleCalculatorKJ")
        wf.edges.append(VibeEdge("1897", "0", "1918", "INT"))
        wf.edges.append(VibeEdge("1919", "0", "1900", "0"))
        wf.edges.append(VibeEdge("1919", "0", "1899", "0"))

        # ── Oracle 1904/1758/1784/1865/1893/1920: audio_tts chain with Reroute ──
        # AudioEnhancementNode(1904) → SetNode(1758, 'audio_tts')
        # GetNode(1784, 'audio_tts') → Reroute(1865) → [LTXVAudioVAEEncode(1893), SubgraphStub(1920)]
        wf.nodes["1904"] = VibeNode("1904", "AudioEnhancementNode")
        wf.nodes["1758"] = VibeNode("1758", "SetNode", widgets={"widget_0": "audio_tts"})
        wf.nodes["1784"] = VibeNode("1784", "GetNode", widgets={"widget_0": "audio_tts"})
        wf.nodes["1865"] = VibeNode("1865", "Reroute")
        wf.nodes["1893"] = VibeNode("1893", "LTXVAudioVAEEncode")
        wf.nodes["1920"] = VibeNode("1920", "SubgraphStub")
        wf.edges.append(VibeEdge("1904", "0", "1758", "AUDIO"))
        wf.edges.append(VibeEdge("1784", "0", "1865", ""))
        wf.edges.append(VibeEdge("1865", "0", "1893", "audio"))
        wf.edges.append(VibeEdge("1865", "0", "1920", "0"))

        return wf

    def test_t2v_mode_boolean_registered_as_public_input(self) -> None:
        """Oracle 1862: PrimitiveBoolean(False) chain registers 't2v_mode' as public input."""
        wf = self._build_oracle_wf()
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)

        assert "t2v_mode" in ri
        assert ri["t2v_mode"] == ("9001", "t2v_mode")
        assert "t2v_mode" in wf.inputs
        assert wf.inputs["t2v_mode"].value is False
        assert wf.nodes["9001"].inputs["t2v_mode"] is False

    def test_enhance_prompt_boolean_registered_as_public_input(self) -> None:
        """Oracle 1929: PrimitiveBoolean(True) chain registers 'enhance_prompt' as public input."""
        wf = self._build_oracle_wf()
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)

        assert "enhance_prompt" in ri
        assert ri["enhance_prompt"] == ("9002", "enhance_prompt")
        assert "enhance_prompt" in wf.inputs
        assert wf.inputs["enhance_prompt"].value is True
        assert wf.nodes["9002"].inputs["enhance_prompt"] is True

    def test_fps_primitive_float_single_consumer(self) -> None:
        """Oracle 1586/1577/1871/1651: PrimitiveFloat(24.0) → 'fps' → single consumer."""
        wf = self._build_oracle_wf()
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)

        assert "fps" in ri
        assert ri["fps"] == ("1651", "a")
        assert "fps" in wf.inputs
        assert wf.inputs["fps"].value == pytest.approx(24.0)
        assert wf.nodes["1651"].inputs["a"] == pytest.approx(24.0)

    def test_frames_seconds_multi_consumer_no_register_input(self) -> None:
        """Oracle 1897/1918/1919: non-primitive source → 'frames_seconds' → two consumers."""
        wf = self._build_oracle_wf()
        ri: dict[str, tuple[str, str]] = {}
        resolve_helpers(wf, ri)

        # frames_seconds comes from SimpleCalculatorKJ (not a Primitive*), no literal to fold.
        # Phase A rewrites GetNode(1919) edges to point at SimpleCalculatorKJ(1897).
        assert "frames_seconds" not in ri
        assert "frames_seconds" not in wf.inputs
        edges_to_1900 = [e for e in wf.edges if e.to_node == "1900"]
        edges_to_1899 = [e for e in wf.edges if e.to_node == "1899"]
        assert any(e.from_node == "1897" for e in edges_to_1900)
        assert any(e.from_node == "1897" for e in edges_to_1899)

    def test_audio_tts_reroute_chain_resolved(self) -> None:
        """Oracle 1784/1865: GetNode('audio_tts') → Reroute(1865) resolved to AudioEnhancementNode."""
        wf = self._build_oracle_wf()
        resolve_helpers(wf, {})

        # Reroute 1865 and GetNode 1784 removed
        assert "1865" not in wf.nodes
        assert "1784" not in wf.nodes
        # Consumers (1893 and 1920) now fed from AudioEnhancementNode(1904)
        edges_to_1893 = [e for e in wf.edges if e.to_node == "1893"]
        edges_to_1920 = [e for e in wf.edges if e.to_node == "1920"]
        assert any(e.from_node == "1904" for e in edges_to_1893)
        assert any(e.from_node == "1904" for e in edges_to_1920)

    def test_all_oracle_helper_nodes_removed(self) -> None:
        """All oracle helper nodes are deleted after full resolution."""
        wf = self._build_oracle_wf()
        resolve_helpers(wf, {})

        expected_removed = {
            "1862", "1861",          # PrimitiveBoolean + SetNode (t2v_mode)
            "1929", "1930",          # PrimitiveBoolean + SetNode (enhance_prompt)
            "9003", "9004",          # GetNodes (t2v_mode, enhance_prompt)
            "1586", "1577", "1871",  # PrimitiveFloat + SetNode + GetNode (fps)
            "1918", "1919",          # SetNode + GetNode (frames_seconds)
            "1758", "1784", "1865",  # SetNode + GetNode + Reroute (audio_tts)
        }
        for nid in expected_removed:
            assert nid not in wf.nodes, f"helper node {nid!r} should have been removed"

    def test_non_helper_nodes_survive(self) -> None:
        """Runtime nodes (SourceNode, KSampler, etc.) are not removed."""
        wf = self._build_oracle_wf()
        resolve_helpers(wf, {})

        expected_surviving = {"9001", "9002", "1651", "1897", "1900", "1899", "1904", "1893", "1920"}
        for nid in expected_surviving:
            assert nid in wf.nodes, f"runtime node {nid!r} should have survived"

    def test_oracle_registered_inputs_deterministic(self) -> None:
        """Registered inputs from two independent resolve_helpers calls are identical."""
        ri1: dict[str, tuple[str, str]] = {}
        ri2: dict[str, tuple[str, str]] = {}
        resolve_helpers(self._build_oracle_wf(), ri1)
        resolve_helpers(self._build_oracle_wf(), ri2)
        assert ri1 == ri2
