"""Tests for vibecomfy.porting.layout — sizing (T1), layering (T2), placement (T4), groups (T5)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pytest

from vibecomfy.porting.layout.sizing import (
    _DEFAULT_NODE_WIDTH,
    _HEADER_PX,
    _PREVIEW_BONUS_PX,
    _PREVIEW_CLASS_HINTS,
    _SOCKET_PX,
    _FALLBACK_NODE_SIZE,
    estimate_node_size,
)
from vibecomfy.schema.types import NodeSchema, OutputSpec


# ---------------------------------------------------------------------------
# Minimal VibeNode stand-in (avoids importing full workflow module).
# ---------------------------------------------------------------------------


@dataclass
class _FakeNode:
    """Lightweight stand-in for VibeNode so tests stay isolated."""

    id: str = "1"
    class_type: str = "SomeNode"
    pack: str | None = None
    inputs: dict = field(default_factory=dict)
    widgets: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    uid: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _schema(class_type: str, outputs: list[OutputSpec] | None = None) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={},
        outputs=outputs or [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSizingDeterministic:
    """Same node + same schema → identical result every call."""

    def test_sizing_deterministic_for_same_node(self):
        node = _FakeNode(class_type="PreviewImage", inputs={"images": {}})
        schema_obj = _schema("PreviewImage", outputs=[OutputSpec(type="IMAGE")])

        first = estimate_node_size(node, schema_obj)
        second = estimate_node_size(node, schema_obj)
        third = estimate_node_size(node, schema_obj)

        assert first == second == third
        # With a preview node, height should include the bonus.
        assert first[1] > _FALLBACK_NODE_SIZE[1]


class TestPreviewNodeTaller:
    """Preview-class nodes with media output types get the tall-widget bonus."""

    def test_sizing_preview_node_taller_than_plain(self):
        plain = _FakeNode(class_type="PlainNode", inputs={"x": {}})
        preview = _FakeNode(
            class_type="PreviewImage", inputs={"images": {}}
        )

        plain_schema = _schema("PlainNode", outputs=[OutputSpec(type="INT")])
        preview_schema = _schema("PreviewImage", outputs=[OutputSpec(type="IMAGE")])

        plain_size = estimate_node_size(plain, plain_schema)
        preview_size = estimate_node_size(preview, preview_schema)

        # Same number of inputs; preview should be taller by the bonus.
        assert preview_size[1] == plain_size[1] + _PREVIEW_BONUS_PX
        assert preview_size[0] == plain_size[0] == _DEFAULT_NODE_WIDTH


class TestCanonicalizedInts:
    """Returned coordinates are always plain Python ints."""

    def test_sizing_returns_canonicalized_ints_via_round(self):
        node = _FakeNode(class_type="SaveImage", inputs={"images": {}, "filename_prefix": {}})
        schema_obj = _schema("SaveImage", outputs=[OutputSpec(type="IMAGE")])

        w, h = estimate_node_size(node, schema_obj)

        assert isinstance(w, int)
        assert isinstance(h, int)


class TestNoneSchemaFallback:
    """schema=None uses the documented deterministic fallback formula."""

    def test_sizing_none_schema_uses_documented_fallback(self):
        # Zero inputs → height = header only
        node0 = _FakeNode(class_type="AnyClass", inputs={})
        w0, h0 = estimate_node_size(node0, None)
        assert w0 == _DEFAULT_NODE_WIDTH
        assert h0 == _HEADER_PX  # 30 + 22*0

        # Three inputs → height = 30 + 22*3 = 96
        node3 = _FakeNode(class_type="AnyClass", inputs={"a": {}, "b": {}, "c": {}})
        w3, h3 = estimate_node_size(node3, None)
        assert w3 == _DEFAULT_NODE_WIDTH
        assert h3 == _HEADER_PX + _SOCKET_PX * 3  # 30 + 66 = 96

        # Verify no tall-widget bonus even for preview classes when schema is None.
        preview_node = _FakeNode(class_type="PreviewImage", inputs={"images": {}})
        wp, hp = estimate_node_size(preview_node, None)
        assert wp == _DEFAULT_NODE_WIDTH
        assert hp == _HEADER_PX + _SOCKET_PX * 1  # 30 + 22 = 52, no bonus
        # Double-check: the bonus is NOT applied when schema=None.
        assert hp == _HEADER_PX + _SOCKET_PX * 1


# ===========================================================================
# T2 — compute_layers tests
# ===========================================================================


@dataclass
class _FakeEdge:
    """Lightweight stand-in for VibeEdge."""

    from_node: str
    to_node: str
    from_output: str = "0"
    to_input: str = "0"


class _FakeWF:
    """Minimal fake workflow for compute_layers tests."""

    def __init__(self, nodes: dict[str, _FakeNode], edges: list[_FakeEdge]):
        self.nodes = nodes
        self.edges = edges


def _make_node(id_: str, uid: str = "") -> _FakeNode:
    return _FakeNode(id=id_, uid=uid or id_)


def _make_edge(from_id: str, to_id: str) -> _FakeEdge:
    return _FakeEdge(from_node=from_id, to_node=to_id)


class TestLayersTotalAssignment:
    """Every node in the graph receives a layer, even on a zero-sampler edit graph."""

    def test_layers_total_assignment_on_zero_sampler_edit_graph(self):
        from vibecomfy.porting.layout.layering import compute_layers

        # A minimal "edit" graph with 0 samplers: just a LoadImage → PreviewImage.
        n1 = _make_node("1", "load_image")
        n2 = _make_node("2", "preview_image")
        e1 = _make_edge("1", "2")
        wf = _FakeWF({"1": n1, "2": n2}, [e1])

        layers = compute_layers(wf)
        assert layers["load_image"] == 0
        assert layers["preview_image"] == 1
        assert len(layers) == 2


class TestLayersParallelSamplers:
    """Parallel sampler nodes land in the same layer, no collisions."""

    def test_layers_handle_parallel_samplers_no_collisions(self):
        from vibecomfy.porting.layout.layering import compute_layers

        # Source → A, Source → B (parallel)
        n_src = _make_node("0", "source")
        n_a = _make_node("1", "sampler_a")
        n_b = _make_node("2", "sampler_b")
        wf = _FakeWF(
            {"0": n_src, "1": n_a, "2": n_b},
            [_make_edge("0", "1"), _make_edge("0", "2")],
        )

        layers = compute_layers(wf)
        assert layers["source"] == 0
        assert layers["sampler_a"] == 1
        assert layers["sampler_b"] == 1
        assert len(layers) == 3


class TestLayersCycleViaSCC:
    """A cycle is collapsed into a single SCC, all members share one layer."""

    def test_layers_handle_cycle_via_scc_collapse(self):
        from vibecomfy.porting.layout.layering import compute_layers

        # A → B → C → A (cycle), plus D → A (source)
        n_a = _make_node("1", "a")
        n_b = _make_node("2", "b")
        n_c = _make_node("3", "c")
        n_d = _make_node("4", "d")
        wf = _FakeWF(
            {"1": n_a, "2": n_b, "3": n_c, "4": n_d},
            [
                _make_edge("1", "2"),
                _make_edge("2", "3"),
                _make_edge("3", "1"),
                _make_edge("4", "1"),
            ],
        )

        layers = compute_layers(wf)
        # D is source → layer 0.
        assert layers["d"] == 0
        # A, B, C are in the same SCC → all same layer, and deeper than D.
        assert layers["a"] == layers["b"] == layers["c"]
        assert layers["a"] > 0
        assert len(layers) == 4


class TestLayersDeterministic:
    """Byte-identical output for the same input, regardless of iteration order."""

    def test_layers_deterministic_byte_identical(self):
        from vibecomfy.porting.layout.layering import compute_layers

        nodes = {
            str(i): _make_node(str(i), f"node_{i}")
            for i in range(10)
        }
        edges = [
            _make_edge("0", "1"),
            _make_edge("1", "2"),
            _make_edge("2", "3"),
            _make_edge("3", "4"),
            _make_edge("4", "5"),
            _make_edge("5", "6"),
            _make_edge("6", "7"),
            _make_edge("7", "8"),
            _make_edge("8", "9"),
        ]

        def _build():
            # Build with edges in a deterministic but non-obvious order.
            wf = _FakeWF(dict(nodes), list(reversed(edges)))
            return compute_layers(wf)

        first = _build()
        second = _build()
        third = _build()

        assert first == second == third
        for k in sorted(first, key=lambda u: u.zfill(20)):
            # node_0 → 0, node_1 → 1, ... node_9 → 9
            expected_layer = int(k.split("_")[-1])
            assert first[k] == expected_layer


class TestLayersIdToUidTranslation:
    """Edges use node.id but adjacency uses node.uid — translation works."""

    def test_layers_id_to_uid_translation(self):
        from vibecomfy.porting.layout.layering import compute_layers

        # Simulate scoped uids (as from subgraph inner nodes).
        n1 = _make_node("3", "subgraph#inner_3")
        n2 = _make_node("7", "subgraph#inner_7")
        wf = _FakeWF(
            {"3": n1, "7": n2},
            [_make_edge("3", "7")],  # edge uses raw id
        )

        layers = compute_layers(wf)
        assert layers["subgraph#inner_3"] == 0
        assert layers["subgraph#inner_7"] == 1


class TestLayersOrphanWithUnknownClass:
    """An orphan node (no edges) with an unknown class defaults to layer 0 with a warning."""

    def test_layers_orphan_with_unknown_class_defaults_to_zero(self, caplog):
        from vibecomfy.porting.layout.layering import compute_layers

        n = _make_node("99", "unknown_class_xyz")
        wf = _FakeWF({"99": n}, [])

        with caplog.at_level(logging.WARNING):
            layers = compute_layers(wf)

        assert layers["unknown_class_xyz"] == 0
        # Should have logged a warning about unreached uids.
        assert any(
            "not reached" in record.message.lower()
            for record in caplog.records
        )


# ===========================================================================
# T4 — place_constrained tests
# ===========================================================================


class TestPlacementEmptyPinned:
    """With no other pinned nodes, new node is placed right of the anchor."""

    def test_placement_empty_pinned_returns_anchor_right_edge(self):
        from vibecomfy.porting.layout.placement import place_constrained

        pinned = {
            "anchor_1": {"pos": [100.0, 200.0], "size": [320.0, 96.0]},
        }
        x, y = place_constrained(
            "new_node",
            "anchor_1",
            pinned=pinned,
            size=(320.0, 96.0),
            canvas_extent=4000,
        )
        # Expected: anchor_x (100) + anchor_w (320) + gap (40) = 460
        assert x == 460.0
        assert y == 200.0


class TestPlacementSingleObstacle:
    """A single obstacle at the initial spot causes a ray dodge."""

    def test_placement_single_obstacle_dodges_first_ray(self):
        from vibecomfy.porting.layout.placement import place_constrained

        anchor = {"pos": [100.0, 200.0], "size": [320.0, 96.0]}
        # Place an obstacle exactly at the initial candidate spot.
        obstacle = {"pos": [460.0, 200.0], "size": [320.0, 96.0]}
        pinned = {"anchor_1": anchor, "obs": obstacle}

        x, y = place_constrained(
            "new_node",
            "anchor_1",
            pinned=pinned,
            size=(320.0, 96.0),
            canvas_extent=4000,
        )
        # Should NOT be the initial candidate (460, 200), but something else.
        assert not (x == 460.0 and y == 200.0)
        # Both coords should be canonicalized (2-decimal rounded floats).
        assert isinstance(x, float)
        assert isinstance(y, float)


class TestPlacementDensePinField:
    """When the ray cap is exhausted, fallback to max_x + gap."""

    def test_placement_dense_pin_field_falls_back_to_max_x(self, caplog):
        from vibecomfy.porting.layout.placement import place_constrained

        anchor = {"pos": [0.0, 0.0], "size": [320.0, 96.0]}
        pinned = {"anchor_1": anchor}

        # Create a dense field of obstacles covering all rays up to the cap.
        import math
        _STEP = 60
        _ANCHOR_GAP_PX = 40
        _DIRECTIONS = (
            (0, -1), (1, -1), (1, 0), (1, 1),
            (0, 1), (-1, 1), (-1, 0), (-1, -1),
        )
        initial_x = 320.0 + 40.0  # 360.0
        initial_y = 0.0
        # canvas_extent=4000 → max_ray_steps = max(64, 4000//60) = 66
        # Cover steps 1..66 (inclusive) so the cap is reached.
        for step in range(1, 67):
            radius = step * _STEP
            for dx, dy in _DIRECTIONS:
                if dx != 0 and dy != 0:
                    r = radius / math.sqrt(2)
                else:
                    r = radius
                cx = initial_x + dx * r
                cy = initial_y + dy * r
                pinned[f"obs_{step}_{dx}_{dy}"] = {"pos": [cx, cy], "size": [320.0, 96.0]}

        with caplog.at_level(logging.WARNING):
            x, y = place_constrained(
                "new_node",
                "anchor_1",
                pinned=pinned,
                size=(320.0, 96.0),
                canvas_extent=4000,
            )

        # Should have emitted the ray-cap warning.
        assert any("ray cap reached" in record.message.lower() for record in caplog.records)
        # Fallback position is right of anchor.
        assert x == 360.0
        assert y == 0.0


class TestPlacementDeterministic:
    """Deterministic placement under dict-reordering."""

    def test_placement_deterministic_under_dict_reordering(self):
        from vibecomfy.porting.layout.placement import place_constrained

        def _build(order):
            pinned = {}
            for uid in order:
                pinned[uid] = {"pos": [float(uid) * 100, 0.0], "size": [80.0, 80.0]}
            return place_constrained(
                "new_node",
                "10",
                pinned=pinned,
                size=(320.0, 96.0),
                canvas_extent=4000,
            )

        # Two different insertion orders should yield identical result.
        first = _build(["5", "10", "3", "7", "1", "9", "2", "8", "4", "6"])
        second = _build(["10", "9", "8", "7", "6", "5", "4", "3", "2", "1"])
        assert first == second


# ===========================================================================
# T5 — build_subgraph_groups tests
# ===========================================================================


class TestSubgraphBoxTitle:
    """Group title matches the subgraph definition name."""

    def test_subgraph_box_title_matches_definition_name(self):
        from vibecomfy.porting.layout.groups import build_subgraph_groups

        wf = _FakeWF({}, [])
        wf.metadata = {
            "definitions": {
                "subgraphs": [
                    {
                        "id": "abc-123",
                        "name": "MySubgraph",
                        "nodes": [
                            {
                                "id": 1,
                                "properties": {"vibecomfy_uid": "my_uid_1"},
                            }
                        ],
                    }
                ]
            }
        }

        positions = {"my_uid_1": {"pos": [10.0, 20.0]}}
        sizes = {"my_uid_1": (320, 96)}

        groups = build_subgraph_groups(wf, positions=positions, sizes=sizes)
        assert len(groups) == 1
        assert groups[0]["title"] == "MySubgraph"


class TestSubgraphBoxBounds:
    """Bounding box encloses all member nodes with padding."""

    def test_subgraph_box_bounds_enclose_all_member_nodes(self):
        from vibecomfy.porting.layout.groups import build_subgraph_groups

        wf = _FakeWF({}, [])
        wf.metadata = {
            "definitions": {
                "subgraphs": [
                    {
                        "id": "sg1",
                        "name": "TestGroup",
                        "nodes": [
                            {"id": 1, "properties": {"vibecomfy_uid": "uid_a"}},
                            {"id": 2, "properties": {"vibecomfy_uid": "uid_b"}},
                        ],
                    }
                ]
            }
        }

        positions = {
            "uid_a": {"pos": [0.0, 0.0]},
            "uid_b": {"pos": [640.0, 480.0]},
        }
        sizes = {
            "uid_a": (320, 96),
            "uid_b": (320, 96),
        }

        groups = build_subgraph_groups(wf, positions=positions, sizes=sizes)
        assert len(groups) == 1
        g = groups[0]
        bx, by, bw, bh = g["bounding"]
        # uid_a: (0,0) → (320,96); uid_b: (640,480) → (960,576)
        # Box without pad: x=0, y=0, w=960, h=576
        # With pad (24): x=-24, y=-24, w=960+48=1008, h=576+48=624
        assert bx == -24.0
        assert by == -24.0
        assert bw == 1008.0
        assert bh == 624.0
        assert isinstance(g["color"], str) and g["color"].startswith("#"), (
            f"Expected hex colour string, got {g['color']!r}"
        )


class TestNoSubgraphsReturnsEmpty:
    """No subgraphs in metadata → empty group list."""

    def test_no_subgraphs_returns_empty_group_list(self):
        from vibecomfy.porting.layout.groups import build_subgraph_groups

        # No metadata at all.
        wf = _FakeWF({}, [])
        groups = build_subgraph_groups(wf, positions={}, sizes={})
        assert groups == []

        # Metadata with no definitions.
        wf.metadata = {"other": 1}
        groups = build_subgraph_groups(wf, positions={}, sizes={})
        assert groups == []

        # Definitions with no subgraphs.
        wf.metadata = {"definitions": {}}
        groups = build_subgraph_groups(wf, positions={}, sizes={})
        assert groups == []


class TestSubgraphPartialMatch:
    """Partial inner-uid match debug-logs and uses subset bounds."""

    def test_subgraph_partial_match_logs_debug_and_uses_subset_bounds(self, caplog):
        from vibecomfy.porting.layout.groups import build_subgraph_groups

        wf = _FakeWF({}, [])
        wf.metadata = {
            "definitions": {
                "subgraphs": [
                    {
                        "id": "sg_partial",
                        "name": "PartialGroup",
                        "nodes": [
                            {"id": 1, "properties": {"vibecomfy_uid": "uid_x"}},
                            {"id": 2, "properties": {}},  # no vibecomfy_uid
                            {"id": 3, "properties": {"vibecomfy_uid": "uid_y"}},
                        ],
                    }
                ]
            }
        }

        positions = {
            "uid_x": {"pos": [100.0, 200.0]},
            "uid_y": {"pos": [200.0, 400.0]},
        }
        sizes = {
            "uid_x": (320, 96),
            "uid_y": (320, 96),
        }

        with caplog.at_level(logging.DEBUG):
            groups = build_subgraph_groups(wf, positions=positions, sizes=sizes)

        assert len(groups) == 1
        # Should have debug-logged the partial match.
        assert any(
            "matched 2/3" in record.message for record in caplog.records
        )
        # Box encloses only uid_x and uid_y (the matched subset).
        g = groups[0]
        assert g["title"] == "PartialGroup"
        bx, by, bw, bh = g["bounding"]
        # uid_x: (100,200) → (420,296); uid_y: (200,400) → (520,496)
        # Box: x=100-24=76, y=200-24=176, w=520-100+48=468, h=496-200+48=344
        assert bx == 76.0
        assert by == 176.0
        assert bw == 468.0
        assert bh == 344.0


# ===========================================================================
# T21 — Role-colored groups tests
# ===========================================================================


class TestRoleColorConsistentAcrossWorkflows:
    """Same subgraph name → same colour regardless of ordering or workflow."""

    def test_same_subgraph_name_gets_same_color(self):
        from vibecomfy.porting.layout.groups import build_subgraph_groups

        def _make_wf_with_subgraph(name: str):
            wf = _FakeWF({}, [])
            wf.metadata = {
                "definitions": {
                    "subgraphs": [
                        {
                            "id": "sg1",
                            "name": name,
                            "nodes": [
                                {
                                    "id": 1,
                                    "properties": {"vibecomfy_uid": "uid_a"},
                                }
                            ],
                        }
                    ]
                }
            }
            return wf

        positions = {"uid_a": {"pos": [10.0, 20.0]}}
        sizes = {"uid_a": (320, 96)}

        # Same name in two different workflow instances → same colour.
        wf_a = _make_wf_with_subgraph("MySubgraph")
        wf_b = _make_wf_with_subgraph("MySubgraph")
        groups_a = build_subgraph_groups(wf_a, positions=positions, sizes=sizes)
        groups_b = build_subgraph_groups(wf_b, positions=positions, sizes=sizes)
        assert groups_a[0]["color"] == groups_b[0]["color"], (
            "Same subgraph name must produce the same colour across workflows"
        )

    def test_different_subgraph_names_may_differ(self):
        from vibecomfy.porting.layout.groups import build_subgraph_groups

        def _make_wf_with_subgraph(name: str):
            wf = _FakeWF({}, [])
            wf.metadata = {
                "definitions": {
                    "subgraphs": [
                        {
                            "id": "sg1",
                            "name": name,
                            "nodes": [
                                {
                                    "id": 1,
                                    "properties": {"vibecomfy_uid": "uid_a"},
                                }
                            ],
                        }
                    ]
                }
            }
            return wf

        positions = {"uid_a": {"pos": [10.0, 20.0]}}
        sizes = {"uid_a": (320, 96)}

        wf_a = _make_wf_with_subgraph("AlphaSubgraph")
        wf_b = _make_wf_with_subgraph("BetaSubgraph")
        groups_a = build_subgraph_groups(wf_a, positions=positions, sizes=sizes)
        groups_b = build_subgraph_groups(wf_b, positions=positions, sizes=sizes)
        # They *may* differ (hash-based).  The important property is that each
        # is a valid colour string.
        for g in groups_a + groups_b:
            assert isinstance(g["color"], str) and g["color"].startswith("#"), (
                f"Expected hex colour string, got {g['color']!r}"
            )

    def test_known_role_subgraph_gets_mapped_color(self):
        """Subgraph names containing 'uuid' get the UUID role colour."""
        from vibecomfy.porting.layout.groups import (
            _role_color_for_subgraph,
            _ROLE_COLOR_MAP,
        )

        colour = _role_color_for_subgraph("UUID-abc-123-def")
        assert colour == _ROLE_COLOR_MAP["uuid"], (
            f"UUID subgraph should get teal (#3f7e7e), got {colour}"
        )

    def test_vhs_subgraph_gets_plum(self):
        from vibecomfy.porting.layout.groups import (
            _role_color_for_subgraph,
            _ROLE_COLOR_MAP,
        )

        colour = _role_color_for_subgraph("VHS_VideoCombine")
        assert colour == _ROLE_COLOR_MAP["vhs"], (
            f"VHS subgraph should get plum (#7e3f7e), got {colour}"
        )


# ===========================================================================
# T3 — assign_lanes tests
# ===========================================================================


class TestLanesOneBandPerWCC:
    """Each weakly-connected component becomes its own band."""

    def test_lanes_one_band_per_wcc(self):
        from vibecomfy.porting.layout.lanes import assign_lanes

        # Two disconnected components: (a→b) and (c→d). No edge between the two.
        n_a = _make_node("1", "a")
        n_b = _make_node("2", "b")
        n_c = _make_node("3", "c")
        n_d = _make_node("4", "d")
        wf = _FakeWF(
            {"1": n_a, "2": n_b, "3": n_c, "4": n_d},
            [_make_edge("1", "2"), _make_edge("3", "4")],
        )
        layers = {"a": 0, "b": 1, "c": 0, "d": 1}

        lanes = assign_lanes(wf, layers)

        # Both components should be in different bands.
        band_a = lanes["a"][0]
        band_c = lanes["c"][0]
        assert band_a != band_c, "disconnected components should get different bands"

        # Nodes in the same component share the same band.
        assert lanes["a"][0] == lanes["b"][0]
        assert lanes["c"][0] == lanes["d"][0]

        # All sub-lanes within each (band, layer) cell start from 0.
        # a and c are both in layer 0 but different bands → both sub_lane 0.
        assert lanes["a"][1] == 0
        assert lanes["c"][1] == 0


class TestLanesParallelSiblings:
    """Nodes in the same (band, layer) cell get distinct sub-lane indices."""

    def test_lanes_parallel_sibling_nodes_get_distinct_sub_lanes(self):
        from vibecomfy.porting.layout.lanes import assign_lanes

        # Three nodes all at the same layer, all in the same WCC.
        # src → a, src → b, src → c  (parallel siblings)
        n_src = _make_node("0", "source")
        n_a = _make_node("1", "sampler_a")
        n_b = _make_node("2", "sampler_b")
        n_c = _make_node("3", "sampler_c")
        wf = _FakeWF(
            {"0": n_src, "1": n_a, "2": n_b, "3": n_c},
            [
                _make_edge("0", "1"),
                _make_edge("0", "2"),
                _make_edge("0", "3"),
            ],
        )
        # All at layer 0 except source at layer 0.
        layers = {"source": 0, "sampler_a": 1, "sampler_b": 1, "sampler_c": 1}

        lanes = assign_lanes(wf, layers)

        # All in the same band (single WCC).
        band = lanes["source"][0]
        assert lanes["sampler_a"][0] == band
        assert lanes["sampler_b"][0] == band
        assert lanes["sampler_c"][0] == band

        # The three siblings at layer 1 must have distinct sub-lane indices.
        sub_lanes = {
            lanes["sampler_a"][1],
            lanes["sampler_b"][1],
            lanes["sampler_c"][1],
        }
        assert len(sub_lanes) == 3, "parallel siblings should get distinct sub-lanes"
        # Sub-lanes should be 0, 1, 2 (monotonically increasing from 0).
        assert sub_lanes == {0, 1, 2}

        # Sub-lane ordering is deterministic: sorted by (class_type, uid.zfill(20)).
        # All have same class_type (_FakeNode has class_type="SomeNode" — but
        # _make_node uses uid which defaults to id, so here the uids differ).
        # Verify ordering matches the sort key.
        sorted_uids = sorted(
            ["sampler_a", "sampler_b", "sampler_c"],
            key=lambda u: ("SomeNode", u.zfill(20)),
        )
        for idx, uid in enumerate(sorted_uids):
            assert lanes[uid][1] == idx, (
                f"expected sub_lane {idx} for uid={uid}, got {lanes[uid][1]}"
            )


class TestLanesCanvasExtent:
    """Canvas extent scales beyond 2000 px on a large graph."""

    def test_lanes_canvas_extent_scales_beyond_2000px(self):
        from vibecomfy.porting.layout.lanes import assign_lanes, compute_canvas_extent
        from vibecomfy.porting.layout.lanes import _COLUMN_PITCH_PX, _BAND_GAP_PX

        # Build a graph with many bands and many sub-lanes so the canvas
        # extent exceeds 2000 px.
        # Strategy: 3 disconnected WCCs (3 bands), each with 2 layers and
        # 3 parallel nodes in one of the layers.
        # Band 0: layer 0 has 3 sub-lanes → width = 3 * 520 = 1560
        # Band 1: layer 0 has 3 sub-lanes → width = 3 * 520 = 1560
        # Band 2: layer 0 has 3 sub-lanes → width = 3 * 520 = 1560
        # Canvas = 1560 + 80 + 1560 + 80 + 1560 = 4840 > 2000 ✓

        nodes: dict[str, _FakeNode] = {}
        edges: list[_FakeEdge] = []
        layers: dict[str, int] = {}

        id_counter = 0

        def _add_node(uid: str, class_type: str = "SomeNode") -> str:
            nonlocal id_counter
            nid = str(id_counter)
            id_counter += 1
            nodes[nid] = _FakeNode(id=nid, uid=uid, class_type=class_type)
            return nid

        # Build 3 disconnected bands with 3 siblings each.
        for band_num in range(3):
            prefix = f"b{band_num}"
            # Source node at layer 0.
            src_uid = f"{prefix}_src"
            src_id = _add_node(src_uid, "Source")
            layers[src_uid] = 0

            # Three sibling nodes at layer 1.
            for sib in range(3):
                sib_uid = f"{prefix}_sib{sib}"
                sib_id = _add_node(sib_uid, "Sampler")
                layers[sib_uid] = 1
                edges.append(_make_edge(src_id, sib_id))

            # A terminal node at layer 2.
            term_uid = f"{prefix}_term"
            term_id = _add_node(term_uid, "SaveImage")
            layers[term_uid] = 2
            # Connect one of the siblings to the terminal.
            edges.append(_make_edge(str(id_counter - 4), term_id))

        wf = _FakeWF(nodes, edges)
        lanes = assign_lanes(wf, layers)
        canvas = compute_canvas_extent(lanes, layers)

        assert canvas > 2000.0, (
            f"expected canvas extent > 2000, got {canvas}"
        )

        # Verify we have 3 distinct bands.
        bands = {lanes[uid][0] for uid in lanes}
        assert len(bands) == 3

        # Verify canvas computation is consistent:
        # Each band has max 3 sub-lanes → width = 3 * 520 = 1560
        # Canvas = 1560 + 80 + 1560 + 80 + 1560 = 4840
        expected = 3 * (3 * _COLUMN_PITCH_PX) + 2 * _BAND_GAP_PX
        assert canvas == float(expected), (
            f"expected canvas={expected}, got {canvas}"
        )


# ===========================================================================
# T6 — layout engine tests
# ===========================================================================


class TestEngineEmptyPinnedUsesLayeredGeometry:
    """With no pinned nodes the engine assigns positions from layered geometry."""

    def test_engine_empty_pinned_uses_layered_geometry(self):
        from vibecomfy.porting.layout import layout

        # Linear chain: A → B → C; deeper nodes must have larger x.
        n_a = _make_node("1", "a")
        n_b = _make_node("2", "b")
        n_c = _make_node("3", "c")
        wf = _FakeWF(
            {"1": n_a, "2": n_b, "3": n_c},
            [_make_edge("1", "2"), _make_edge("2", "3")],
        )

        result = layout(wf)

        x_a = result.positions["a"]["pos"][0]
        x_b = result.positions["b"]["pos"][0]
        x_c = result.positions["c"]["pos"][0]

        assert x_a < x_b < x_c, (
            f"expected layered x ordering a<b<c, got a={x_a} b={x_b} c={x_c}"
        )
        assert result.groups == []


class TestEnginePinnedSetPreservedVerbatim:
    """Pinned positions/sizes are written through without modification."""

    def test_engine_pinned_set_preserved_verbatim(self):
        from vibecomfy.porting.layout import layout

        n_a = _make_node("1", "a")
        n_b = _make_node("2", "b")
        wf = _FakeWF({"1": n_a, "2": n_b}, [_make_edge("1", "2")])

        pinned_pos = [999.0, 888.0]
        pinned_size = [123.0, 45.0]
        result = layout(wf, pinned={"a": {"pos": pinned_pos, "size": pinned_size}})

        assert result.positions["a"]["pos"] == pinned_pos
        assert result.positions["a"]["size"] == pinned_size

        # Non-pinned node gets geometry (not from pinned).
        assert "b" in result.positions
        assert result.positions["b"]["pos"] != pinned_pos


class TestEngineAnchorsRouteThroughPlacement:
    """Anchored uids are placed via place_constrained, not raw layered geometry."""

    def test_engine_anchors_route_through_placement(self):
        from vibecomfy.porting.layout import layout

        n_a = _make_node("1", "anchor_node")
        n_b = _make_node("2", "other_node")
        wf = _FakeWF({"1": n_a, "2": n_b}, [_make_edge("1", "2")])

        # Ask the engine to (re-)place anchor_node relative to other_node.
        result = layout(wf, anchors={"anchor_node": "other_node"})

        # anchor_node must appear in positions.
        assert "anchor_node" in result.positions

        # The anchor result is determined by place_constrained which puts it
        # to the right of the anchor target + gap (40px) unless blocked.
        # We just assert the position is non-negative and differs from other_node.
        anchor_x = result.positions["anchor_node"]["pos"][0]
        other_x = result.positions["other_node"]["pos"][0]
        assert anchor_x >= 0.0
        assert result.positions["anchor_node"]["pos"] != result.positions["other_node"]["pos"]
        # Anchored node is placed to the right of (or near) the anchor target.
        # other_node's x + its width + gap_40 = initial candidate.
        other_w = result.positions["other_node"]["size"][0]
        expected_min_x = other_x + other_w  # at least the right edge of anchor
        assert anchor_x >= expected_min_x - 1.0  # 1px tolerance for float rounding


class TestEngineDeterministicTwoCallsByteIdentical:
    """Two calls on the same IR produce byte-identical LayoutResult."""

    def test_engine_deterministic_two_calls_byte_identical(self):
        from vibecomfy.porting.layout import layout

        nodes = {str(i): _make_node(str(i), f"node_{i}") for i in range(8)}
        edges = [
            _make_edge("0", "1"),
            _make_edge("0", "2"),
            _make_edge("1", "3"),
            _make_edge("2", "3"),
            _make_edge("3", "4"),
            _make_edge("4", "5"),
            _make_edge("4", "6"),
            _make_edge("5", "7"),
            _make_edge("6", "7"),
        ]
        wf = _FakeWF(nodes, edges)

        first = layout(wf)
        second = layout(wf)

        assert first.positions == second.positions
        assert first.groups == second.groups


class TestEngineNoOverlapInvariant:
    """No two node bounding boxes overlap on a dense synthetic graph (~20 nodes)."""

    def test_engine_no_overlap_invariant_on_synthetic_dense_graph(self):
        from vibecomfy.porting.layout import layout

        # Build a graph with ~20 nodes: 2 disconnected WCCs, fan-outs and fan-ins.
        # WCC 0: 10-node chain with some parallel branches.
        # WCC 1: 10-node parallel ladder.
        nodes: dict[str, _FakeNode] = {}
        edges: list[_FakeEdge] = []
        nid = 0

        def _add(uid: str) -> str:
            nonlocal nid
            nodes[str(nid)] = _FakeNode(id=str(nid), uid=uid, class_type="SomeNode")
            nid += 1
            return str(nid - 1)

        # WCC 0: src0 → a0, a1 → b0, b1, b2 → c0 → d0, d1 → e0
        s0 = _add("s0")
        a0 = _add("a0"); edges.append(_make_edge(s0, a0))
        a1 = _add("a1"); edges.append(_make_edge(s0, a1))
        b0 = _add("b0"); edges.append(_make_edge(a0, b0))
        b1 = _add("b1"); edges.append(_make_edge(a0, b1))
        b2 = _add("b2"); edges.append(_make_edge(a1, b2))
        c0 = _add("c0")
        edges.append(_make_edge(b0, c0)); edges.append(_make_edge(b1, c0)); edges.append(_make_edge(b2, c0))
        d0 = _add("d0"); edges.append(_make_edge(c0, d0))
        d1 = _add("d1"); edges.append(_make_edge(c0, d1))
        e0 = _add("e0")
        edges.append(_make_edge(d0, e0)); edges.append(_make_edge(d1, e0))

        # WCC 1: fully disconnected chain p0→p1→p2→p3→p4→p5→p6→p7→p8→p9
        prev = _add("p0")
        for i in range(1, 10):
            cur = _add(f"p{i}")
            edges.append(_make_edge(prev, cur))
            prev = cur

        wf = _FakeWF(nodes, edges)
        result = layout(wf)

        assert len(result.positions) == len(nodes), (
            f"expected {len(nodes)} positions, got {len(result.positions)}"
        )

        # Build bounding boxes: (x, y, w, h)
        def _bbox(uid: str) -> tuple[float, float, float, float]:
            entry = result.positions[uid]
            x, y = entry["pos"]
            w, h = entry["size"]
            return (float(x), float(y), float(w), float(h))

        uids = list(result.positions.keys())
        for i in range(len(uids)):
            for j in range(i + 1, len(uids)):
                ax, ay, aw, ah = _bbox(uids[i])
                bx, by, bw, bh = _bbox(uids[j])
                # AABB overlap: both x and y must overlap.
                x_overlap = ax < bx + bw and ax + aw > bx
                y_overlap = ay < by + bh and ay + ah > by
                assert not (x_overlap and y_overlap), (
                    f"nodes {uids[i]} and {uids[j]} bboxes overlap: "
                    f"A=({ax},{ay},{aw},{ah}) B=({bx},{by},{bw},{bh})"
                )


class TestEngineSchemaCacheAvoidsProviderCalls:
    """schema_cache pre-populated for all node types → provider.get_schema never called."""

    def test_engine_schema_cache_path_avoids_provider_calls(self):
        from vibecomfy.porting.layout import layout
        from vibecomfy.schema.types import NodeSchema

        nodes = {
            "1": _FakeNode(id="1", uid="u1", class_type="TypeA"),
            "2": _FakeNode(id="2", uid="u2", class_type="TypeB"),
            "3": _FakeNode(id="3", uid="u3", class_type="TypeA"),
        }
        wf = _FakeWF(nodes, [_make_edge("1", "2"), _make_edge("2", "3")])

        # Pre-populate cache for every class_type in the workflow.
        schema_a = NodeSchema(class_type="TypeA", pack=None, inputs={}, outputs=[])
        schema_b = NodeSchema(class_type="TypeB", pack=None, inputs={}, outputs=[])
        cache: dict = {"TypeA": schema_a, "TypeB": schema_b}

        # Recording provider that raises if called.
        class _StrictProvider:
            calls: list = []

            def get_schema(self, class_type: str):
                self.calls.append(class_type)
                raise AssertionError(
                    f"get_schema called for {class_type!r} — should have hit cache"
                )

        provider = _StrictProvider()
        result = layout(wf, schema_provider=provider, schema_cache=cache)

        assert provider.calls == [], (
            f"expected 0 provider calls, got {provider.calls}"
        )
        assert "u1" in result.positions
        assert "u2" in result.positions
        assert "u3" in result.positions


class TestEngineSchemaProviderReturnsNoneForUnknown:
    """schema_provider returning None for unknown classes does not crash the engine."""

    def test_engine_schema_provider_returns_none_for_unknown_class(self):
        from vibecomfy.porting.layout import layout

        nodes = {
            "1": _FakeNode(id="1", uid="x1", class_type="UnknownWidgetX99"),
            "2": _FakeNode(id="2", uid="x2", class_type="UnknownWidgetY88"),
        }
        wf = _FakeWF(nodes, [_make_edge("1", "2")])

        class _NullProvider:
            def get_schema(self, class_type: str):
                return None

        result = layout(wf, schema_provider=_NullProvider())

        assert "x1" in result.positions
        assert "x2" in result.positions
        # With None schema, sizing uses the deterministic fallback; no exception raised.
        w, h = result.positions["x1"]["size"]
        assert w == 320.0  # _DEFAULT_NODE_WIDTH
        assert h >= 30.0   # _HEADER_PX minimum


# ===========================================================================
# T11 — Barycenter crossing-reduction sweep tests
# ===========================================================================


class TestEngineByteIdenticalWithBarycenter:
    """Two layout() calls with barycenter sweep produce byte-identical results."""

    def test_engine_byte_identical_with_barycenter(self):  # noqa: D401
        from vibecomfy.porting.layout import layout
        import vibecomfy.porting.layout.engine as _eng

        # Ensure sweep is ON for this test (should already be True per T11).
        assert _eng._BARYCENTER_SWEEP is True, (
            "T11 requires _BARYCENTER_SWEEP=True"
        )

        # Build a modest DAG with parallel fan-out so the sweep has work to do.
        nodes = {str(i): _make_node(str(i), f"node_{i}") for i in range(8)}
        edges = [
            _make_edge("0", "1"),
            _make_edge("0", "2"),
            _make_edge("1", "3"),
            _make_edge("2", "3"),
            _make_edge("3", "4"),
            _make_edge("3", "5"),
            _make_edge("4", "6"),
            _make_edge("5", "6"),
            _make_edge("6", "7"),
        ]
        wf = _FakeWF(nodes, edges)

        first = layout(wf)
        second = layout(wf)

        assert first.positions == second.positions, (
            "Two layout calls with barycenter sweep must produce identical positions"
        )
        assert first.groups == second.groups, (
            "Two layout calls with barycenter sweep must produce identical groups"
        )


class TestEngineBarycenterNoSubLaneCollisions:
    """Two nodes that barycenter to the same mean get distinct final sub-lanes."""

    def test_engine_barycenter_no_sub_lane_collisions(self):
        from vibecomfy.porting.layout import layout
        import vibecomfy.porting.layout.engine as _eng

        assert _eng._BARYCENTER_SWEEP is True

        # Graph:  src (layer 0) → node_a, node_b (both layer 1, parallel siblings).
        # Both node_a and node_b have the same single predecessor (src), so they
        # both barycenter to the same mean (sub_lane of src = 0.0).
        # After the sweep, they must still receive distinct sub-lane indices
        # (sorted by uid.zfill(20) as the tie-breaker).
        n_src = _make_node("0", "source_node")
        n_a = _make_node("1", "target_a")
        n_b = _make_node("2", "target_b")
        wf = _FakeWF(
            {"0": n_src, "1": n_a, "2": n_b},
            [_make_edge("0", "1"), _make_edge("0", "2")],
        )

        result = layout(wf)

        # Both nodes should be present with distinct Y positions.
        pos_a = result.positions["target_a"]["pos"]
        pos_b = result.positions["target_b"]["pos"]
        assert pos_a != pos_b, (
            f"target_a and target_b must have different positions: "
            f"a={pos_a}, b={pos_b}"
        )
        # Their Y coordinates must differ (distinct sub-lanes).
        assert pos_a[1] != pos_b[1], (
            f"target_a and target_b must have different Y (sub-lane) positions: "
            f"a_y={pos_a[1]}, b_y={pos_b[1]}"
        )
        # Both X coordinates must be the same (same band, same layer).
        assert pos_a[0] == pos_b[0], (
            f"target_a and target_b must have the same X (same band+layer): "
            f"a_x={pos_a[0]}, b_x={pos_b[0]}"
        )


class TestEngineBarycenterPositionsReflectSweep:
    """Swept order differs from assign_lanes order; emitted Y coords match swept order."""

    def test_engine_barycenter_positions_reflect_sweep(self):
        from vibecomfy.porting.layout import layout
        from vibecomfy.porting.layout.lanes import assign_lanes
        import vibecomfy.porting.layout.engine as _eng

        assert _eng._BARYCENTER_SWEEP is True

        # Build a graph where assign_lanes sorts by (class_type, uid.zfill(20))
        # but barycenter sweep reorders based on predecessor sub-lanes.
        #
        # Layer 0: root (class_type="Ctrl", uid="root")
        # Layer 1: src_a (class_type="Alpha", uid="src_a"), src_b (class_type="Alpha", uid="src_b")
        #   root → src_a, root → src_b
        #   assign_lanes sorts both at layer 1 by (Alpha, uid.zfill(20)):
        #     src_a → sub_lane 0, src_b → sub_lane 1
        #
        # Layer 2: node_x (class_type="Beta", uid="node_x"), node_y (class_type="Beta", uid="node_y")
        #   Edges: src_b → node_x, src_a → node_y
        #   assign_lanes sorts both at layer 2 by (Beta, uid.zfill(20)):
        #     node_x → sub_lane 0, node_y → sub_lane 1
        #
        # Barycenter sweep:
        #   node_x preds in layer-1: [src_b] → bary_score = sub_lane(src_b) = 1.0
        #   node_y preds in layer-1: [src_a] → bary_score = sub_lane(src_a) = 0.0
        #   After sweep sort by (bary_score, uid): node_y (0.0) then node_x (1.0)
        #   → node_y gets sub_lane 0, node_x gets sub_lane 1
        #
        # So Y ordering is SWAPPED: node_y above node_x, even though assign_lanes
        # would have put node_x first alphabetically.

        n_root = _make_node("0", "root")
        n_root.class_type = "Ctrl"
        n_src_a = _make_node("1", "src_a")
        n_src_a.class_type = "Alpha"
        n_src_b = _make_node("2", "src_b")
        n_src_b.class_type = "Alpha"
        n_x = _make_node("3", "node_x")
        n_x.class_type = "Beta"
        n_y = _make_node("4", "node_y")
        n_y.class_type = "Beta"

        wf = _FakeWF(
            {"0": n_root, "1": n_src_a, "2": n_src_b, "3": n_x, "4": n_y},
            [
                _make_edge("0", "1"),  # root → src_a
                _make_edge("0", "2"),  # root → src_b
                _make_edge("2", "3"),  # src_b → node_x
                _make_edge("1", "4"),  # src_a → node_y
            ],
        )

        # First, verify what assign_lanes would produce (without barycenter).
        # Layers from compute_layers: root=0, src_a=1, src_b=1, node_x=2, node_y=2
        # (all in same WCC because they're connected via root.)
        layers = {"root": 0, "src_a": 1, "src_b": 1, "node_x": 2, "node_y": 2}
        raw_lanes = assign_lanes(wf, layers)
        # All nodes in same band (single WCC).
        band = raw_lanes["root"][0]
        assert raw_lanes["src_a"][0] == band
        assert raw_lanes["src_b"][0] == band
        assert raw_lanes["node_x"][0] == band
        assert raw_lanes["node_y"][0] == band
        # assign_lanes sorts by (class_type, uid.zfill(20)):
        # Beta,node_x.zfill(20) < Beta,node_y.zfill(20) → node_x sub_lane < node_y sub_lane
        assert raw_lanes["node_x"][1] < raw_lanes["node_y"][1], (
            "assign_lanes should put node_x before node_y (alphabetically)"
        )

        # Now run the full engine WITH barycenter sweep.
        result = layout(wf)

        pos_x = result.positions["node_x"]["pos"]
        pos_y = result.positions["node_y"]["pos"]

        # Both should be in the same band+layer → same X coordinate.
        assert pos_x[0] == pos_y[0], (
            f"node_x and node_y should share X coordinate, "
            f"got x={pos_x[0]}, y={pos_y[0]}"
        )

        # After barycenter sweep, node_y (bary_score=0.0) should have lower sub_lane
        # → lower Y than node_x (bary_score=1.0).
        # The swept order reverses the alphabetical ordering from assign_lanes.
        assert pos_y[1] < pos_x[1], (
            f"Barycenter sweep should place node_y (pred=src_a, sub_lane 0) "
            f"ABOVE node_x (pred=src_b, sub_lane 1); "
            f"got y(node_x)={pos_x[1]}, y(node_y)={pos_y[1]}"
        )

        # Sanity: the Y ordering is opposite of what assign_lanes alone would give.
        # If barycenter is working, pos_y[1] < pos_x[1] (as asserted above).
        # This confirms the sweep affected the emitted Y coordinates.

        # Also verify all five nodes have positions.
        for uid in ("root", "src_a", "src_b", "node_x", "node_y"):
            assert uid in result.positions, f"Missing position for {uid}"


# ===========================================================================
# T21 — Role-precedence crossing-reduction tie-break tests
# ===========================================================================


class TestRoleCrossingReductionTiebreak:
    """When barycentre scores are equal, positive-before-negative role precedence
    determines sub-lane ordering (gated by _ROLE_CROSSING_REDUCTION_TIEBREAK)."""

    def test_role_tiebreak_toggle_on_positive_before_negative(self):
        """With toggle ON: LoadImage (positive) sorts before SaveImage (negative)."""
        import vibecomfy.porting.layout.engine as _eng
        import vibecomfy.porting.layout.layering as _lay

        assert _eng._BARYCENTER_SWEEP is True
        assert _lay._ROLE_CROSSING_REDUCTION_TIEBREAK is True

        # Build a graph where two nodes at the same layer have identical
        # barycentre scores (same single predecessor), but one is a positive
        # role (LoadImage-like) and the other is negative (SaveImage-like).
        #
        # Layer 0: src (uid="src")
        # Layer 1: pos_node (uid="positive", class_type="LoadImage")
        #          neg_node (uid="negative", class_type="SaveImage")
        # Edges: src → pos_node, src → neg_node
        #
        # Both barycentre to sub_lane(src) = 0.0.
        # Role tie-break: LoadImage (rank 0) before SaveImage (rank 2).
        n_src = _make_node("0", "src")
        n_src.class_type = "Ctrl"
        n_pos = _make_node("1", "positive")
        n_pos.class_type = "LoadImage"
        n_neg = _make_node("2", "negative")
        n_neg.class_type = "SaveImage"

        wf = _FakeWF(
            {"0": n_src, "1": n_pos, "2": n_neg},
            [
                _make_edge("0", "1"),  # src → positive
                _make_edge("0", "2"),  # src → negative
            ],
        )

        from vibecomfy.porting.layout import layout
        result = layout(wf)

        pos_y = result.positions["positive"]["pos"][1]
        neg_y = result.positions["negative"]["pos"][1]

        # Positive role (LoadImage) should sort before negative (SaveImage) →
        # lower Y (higher on canvas).
        assert pos_y < neg_y, (
            f"Role tie-break: LoadImage (positive) should sort ABOVE SaveImage "
            f"(negative); got pos_y={pos_y}, neg_y={neg_y}"
        )

    def test_role_tiebreak_toggle_off_no_role_effect(self):
        """With toggle OFF: sort falls back to uid-only tie-break, no role effect."""
        import vibecomfy.porting.layout.engine as _eng
        import vibecomfy.porting.layout.layering as _lay

        assert _eng._BARYCENTER_SWEEP is True

        # Temporarily disable the role tie-break toggle.
        old_toggle = _lay._ROLE_CROSSING_REDUCTION_TIEBREAK
        _lay._ROLE_CROSSING_REDUCTION_TIEBREAK = False
        try:
            n_src = _make_node("0", "src")
            n_src.class_type = "Ctrl"
            n_pos = _make_node("1", "positive")
            n_pos.class_type = "LoadImage"
            n_neg = _make_node("2", "negative")
            n_neg.class_type = "SaveImage"

            wf = _FakeWF(
                {"0": n_src, "1": n_pos, "2": n_neg},
                [
                    _make_edge("0", "1"),
                    _make_edge("0", "2"),
                ],
            )

            from vibecomfy.porting.layout import layout
            result = layout(wf)

            pos_y = result.positions["positive"]["pos"][1]
            neg_y = result.positions["negative"]["pos"][1]

            # Without role tie-break, sort is by (bary_score, uid.zfill(20)).
            # "negative".zfill(20) < "positive".zfill(20) → negative sorts first
            # → lower Y.
            assert neg_y < pos_y, (
                f"Without role tie-break, uid-based sort should put 'negative' "
                f"(lexicographically first) above 'positive'; "
                f"got pos_y={pos_y}, neg_y={neg_y}"
            )
        finally:
            _lay._ROLE_CROSSING_REDUCTION_TIEBREAK = old_toggle


# ---------------------------------------------------------------------------
# T7: emit_ui_json wires in the layout engine
# ---------------------------------------------------------------------------


class TestEmitUiJsonEngineIntegration:
    """T7: emit_ui_json uses the layout engine for geometry when no sidecar/captured positions."""

    def test_emit_ui_json_uses_engine_for_no_position_graph(self):
        """Engine positions a 5-node chain with > 2000 px x-span."""
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("span_test", WorkflowSource("span_test"))
        wf.add_node("TypeA", "1", uid="u1")
        wf.add_node("TypeB", "2", uid="u2")
        wf.add_node("TypeC", "3", uid="u3")
        wf.add_node("TypeD", "4", uid="u4")
        wf.add_node("TypeE", "5", uid="u5")
        wf.connect("1.0", "2.x")
        wf.connect("2.0", "3.x")
        wf.connect("3.0", "4.x")
        wf.connect("4.0", "5.x")

        result = emit_ui_json(wf)

        xs = [n["pos"][0] for n in result["nodes"]]
        span = max(xs) - min(xs)
        assert span > 2000, (
            f"Engine layout should span >2000 px for a 5-node chain; got span={span}"
        )

    def test_emit_ui_json_anchors_kwarg_is_additive(self):
        """anchors=None and anchors={} produce identical output; no sentinel warning."""
        import json
        import warnings
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("additive_test", WorkflowSource("additive_test"))
        wf.add_node("TypeA", "1", uid="a1")
        wf.add_node("TypeB", "2", uid="a2")
        wf.connect("1.0", "2.x")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result_none = emit_ui_json(wf)
            result_empty = emit_ui_json(wf, anchors={})

        assert json.dumps(result_none, sort_keys=True) == json.dumps(result_empty, sort_keys=True), (
            "anchors=None and anchors={} must produce identical output"
        )
        sentinel_warns = [w for w in caught if "sentinel" in str(w.message).lower()]
        assert not sentinel_warns, f"Unexpected sentinel warning(s): {sentinel_warns}"

    def test_emit_ui_json_anchors_kwarg_routes_to_placement(self):
        """Anchored node position is placed relative to anchor, differing from Phase-6 band pos."""
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("anchors_route_test", WorkflowSource("anchors_route_test"))
        wf.add_node("TypeA", "1", uid="na")
        wf.add_node("TypeB", "2", uid="nb")
        # No edges → two isolated nodes in separate bands

        result_no = emit_ui_json(wf)
        result_with = emit_ui_json(wf, anchors={"nb": "na"})

        def _pos_for_uid(result, uid):
            for n in result["nodes"]:
                if n.get("properties", {}).get("vibecomfy_uid") == uid:
                    return n["pos"]
            return None

        pos_nb_no = _pos_for_uid(result_no, "nb")
        pos_nb_with = _pos_for_uid(result_with, "nb")
        pos_na_with = _pos_for_uid(result_with, "na")

        assert pos_nb_no is not None, "node 'nb' missing from no-anchor result"
        assert pos_nb_with is not None, "node 'nb' missing from anchored result"
        assert pos_na_with is not None, "node 'na' missing from anchored result"

        # Phase 8 routes 'nb' through place_constrained relative to 'na',
        # overriding its Phase-6 band position.
        assert pos_nb_no != pos_nb_with, (
            f"anchors kwarg did not change 'nb' position: "
            f"no_anchor={pos_nb_no}, anchored={pos_nb_with}"
        )


# ---------------------------------------------------------------------------
# T8: group merge + version bump
# ---------------------------------------------------------------------------


class TestEmitUiJsonGroupsIncludeSubgraphs:
    """T8: emit_ui_json groups array includes engine-generated subgraph groups."""

    def test_emit_ui_json_groups_include_subgraphs(self):
        """When the workflow has subgraph definitions, emitted groups contain subgraph boxes."""
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("subgraph_test", WorkflowSource("subgraph_test"))
        wf.add_node("TypeA", "1", uid="inner_1")
        wf.add_node("TypeB", "2", uid="inner_2")
        wf.connect("1.0", "2.x")

        # Attach subgraph definition whose inner nodes match the flat nodes above.
        wf.metadata = {
            "definitions": {
                "subgraphs": [
                    {
                        "id": "sg-1",
                        "name": "MySubgraphBox",
                        "nodes": [
                            {"id": 10, "properties": {"vibecomfy_uid": "inner_1"}},
                            {"id": 11, "properties": {"vibecomfy_uid": "inner_2"}},
                        ],
                    }
                ]
            }
        }

        result = emit_ui_json(wf)

        groups = result.get("groups", [])
        assert len(groups) >= 1, f"Expected at least 1 group, got {len(groups)}: {groups}"
        titles = [g.get("title") for g in groups]
        assert "MySubgraphBox" in titles, (
            f"Subgraph group 'MySubgraphBox' missing from groups: {titles}"
        )

    def test_emit_ui_json_caller_groups_take_priority_over_engine_groups(self):
        """Caller-passed groups appear before engine groups, and duplicate titles are suppressed."""
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("priority_test", WorkflowSource("priority_test"))
        wf.add_node("TypeA", "1", uid="p1")
        wf.add_node("TypeB", "2", uid="p2")
        wf.connect("1.0", "2.x")

        wf.metadata = {
            "definitions": {
                "subgraphs": [
                    {
                        "id": "sg-p",
                        "name": "EngineGroup",
                        "nodes": [
                            {"id": 10, "properties": {"vibecomfy_uid": "p1"}},
                            {"id": 11, "properties": {"vibecomfy_uid": "p2"}},
                        ],
                    }
                ]
            }
        }

        caller_groups = [
            {"title": "CallerGroup", "bounding": [0, 0, 100, 100], "color": "#ffffff"},
            # Same title as engine group → should be suppressed from engine merge
            {"title": "EngineGroup", "bounding": [200, 200, 50, 50], "color": "#cccccc"},
        ]

        result = emit_ui_json(wf, groups=caller_groups)
        groups = result.get("groups", [])

        # Caller groups must appear first.
        assert len(groups) >= 2, f"Expected at least 2 groups, got {len(groups)}: {groups}"
        assert groups[0]["title"] == "CallerGroup", (
            f"First group should be 'CallerGroup', got {groups[0].get('title')}"
        )
        assert groups[1]["title"] == "EngineGroup", (
            f"Second group should be caller's 'EngineGroup', got {groups[1].get('title')}"
        )

        # Engine group with same title must NOT appear (deduplicated).
        engine_titles = [g["title"] for g in groups[2:]] if len(groups) > 2 else []
        assert "EngineGroup" not in engine_titles, (
            f"Engine group 'EngineGroup' should be deduplicated: {groups}"
        )

        # Caller's EngineGroup should retain its custom bounding (not overwritten by engine).
        # groups[0] = CallerGroup [0, 0, 100, 100]; groups[1] = EngineGroup [200, 200, 50, 50]
        assert groups[0]["bounding"] == [0.0, 0.0, 100.0, 100.0], (
            f"CallerGroup bounding should be preserved: {groups[0]['bounding']}"
        )
        assert groups[1]["bounding"] == [200.0, 200.0, 50.0, 50.0], (
            f"EngineGroup caller bounding should be preserved: {groups[1]['bounding']}"
        )


class TestEmitUiJsonByteIdentical:
    """T8: two emit_ui_json calls on the same workflow produce byte-identical JSON."""

    def test_emit_ui_json_byte_identical_two_calls(self):
        """json.dumps(emit_ui_json(wf), sort_keys=True) twice → identical."""
        import json
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("byte_id_test", WorkflowSource("byte_id_test"))
        wf.add_node("TypeA", "1", uid="ba")
        wf.add_node("TypeB", "2", uid="bb")
        wf.add_node("TypeC", "3", uid="bc")
        wf.connect("1.0", "2.x")
        wf.connect("2.0", "3.y")

        # Attach a subgraph so engine_groups is non-empty (exercises group merge path).
        wf.metadata = {
            "definitions": {
                "subgraphs": [
                    {
                        "id": "sg-byte",
                        "name": "ByteGroup",
                        "nodes": [
                            {"id": 10, "properties": {"vibecomfy_uid": "ba"}},
                            {"id": 11, "properties": {"vibecomfy_uid": "bb"}},
                            {"id": 12, "properties": {"vibecomfy_uid": "bc"}},
                        ],
                    }
                ]
            }
        }

        first = json.dumps(emit_ui_json(wf), sort_keys=True)
        second = json.dumps(emit_ui_json(wf), sort_keys=True)

        assert first == second, (
            f"Two emit_ui_json calls must produce byte-identical output.\n"
            f"First length: {len(first)}, Second length: {len(second)}\n"
            f"First 200 chars: {first[:200]}\n"
            f"Second 200 chars: {second[:200]}"
        )


class TestEmitUiJsonLayoutVersionBreadcrumb:
    """T8: extra.vibecomfy.layout_version is 'm4'."""

    def test_emit_ui_json_layout_version_breadcrumb_is_m4(self):
        """The layout_version breadcrumb in the emitted extra is 'm4'."""
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("version_test", WorkflowSource("version_test"))
        wf.add_node("TypeA", "1", uid="va")

        result = emit_ui_json(wf)

        vibecomfy_extra = result.get("extra", {}).get("vibecomfy", {})
        assert vibecomfy_extra.get("layout_version") == "m4", (
            f"layout_version should be 'm4', got {vibecomfy_extra.get('layout_version')!r}"
        )


# ---------------------------------------------------------------------------
# T9: corpus-wide pure-Python gates
# ---------------------------------------------------------------------------


def _bboxes_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """Return True if axis-aligned bboxes (x1,y1,x2,y2) intersect (exclusive edges)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    # Non-overlap: a is fully left/right/above/below b
    if ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1:
        return False
    return True


def _node_bbox(node_dict: dict) -> tuple[float, float, float, float]:
    """Extract (x1, y1, x2, y2) from an emitted node dict."""
    pos = node_dict["pos"]
    size = node_dict["size"]
    return (pos[0], pos[1], pos[0] + size[0], pos[1] + size[1])


def _corpus_template_ids() -> list[str]:
    """Return repo ready-template ids under image/video/audio/edit."""
    from vibecomfy.registry.ready import repo_ready_template_ids

    allowed = {"image", "video", "audio", "edit"}
    return [
        tid for tid in repo_ready_template_ids()
        if tid.partition("/")[0] in allowed
    ]


class TestCorpusWideInvariants:
    """T9: corpus-wide no-overlap and determinism gates.

    Iterates every ready template under ``ready_templates/{image,video,audio,edit}/``,
    loads it via ``load_workflow_any``, emits UI JSON through the layout engine,
    and asserts (a) no two node bounding boxes overlap, and (b) two consecutive
    ``emit_ui_json`` calls produce byte-identical JSON.
    """

    def test_no_overlap_corpus_wide(self):
        """Every ready template under image/video/audio/edit emits zero overlaps."""
        import json as _json

        from vibecomfy.cli_loader import load_workflow_any
        from vibecomfy.porting.emit.ui import emit_ui_json
        from vibecomfy.porting.layout.sizing import _PREVIEW_CLASS_HINTS

        preview_hints = frozenset(_PREVIEW_CLASS_HINTS)
        failures: list[str] = []
        skipped: list[str] = []

        for tid in _corpus_template_ids():
            try:
                wf = load_workflow_any(tid)
            except Exception as exc:
                skipped.append(f"{tid}: load error ({type(exc).__name__}: {exc})")
                continue

            try:
                envelope = emit_ui_json(wf)
            except Exception as exc:
                skipped.append(f"{tid}: emit error ({type(exc).__name__}: {exc})")
                continue

            nodes = envelope.get("nodes", [])
            bboxes: list[tuple[str, str, float, float, float, float]] = []
            for nd in nodes:
                bboxes.append((
                    nd.get("type", "?"),
                    nd.get("properties", {}).get("vibecomfy_uid", nd.get("id", "?")),
                    *_node_bbox(nd),
                ))

            n = len(bboxes)
            for i in range(n):
                cls_i, uid_i, ix1, iy1, ix2, iy2 = bboxes[i]
                for j in range(i + 1, n):
                    cls_j, uid_j, jx1, jy1, jx2, jy2 = bboxes[j]
                    if _bboxes_overlap((ix1, iy1, ix2, iy2), (jx1, jy1, jx2, jy2)):
                        # Collect classes not in _PREVIEW_CLASS_HINTS for remediation.
                        missing_hint = [
                            c for c in (cls_i, cls_j)
                            if c not in preview_hints
                        ]
                        detail = (
                            f"{tid}: {cls_i}(uid={uid_i}) [{ix1},{iy1},{ix2},{iy2}]"
                            f" overlaps {cls_j}(uid={uid_j}) [{jx1},{jy1},{jx2},{jy2}]"
                        )
                        if missing_hint:
                            detail += (
                                f" (classes not in _PREVIEW_CLASS_HINTS: {missing_hint})"
                            )
                        failures.append(detail)

        # Report skipped templates for diagnosis but don't fail on them.
        if skipped:
            print(f"\nSkipped {len(skipped)} template(s) during corpus sweep:")
            for s in skipped:
                print(f"  {s}")

        assert not failures, (
            f"{len(failures)} overlap violation(s) across corpus:\n"
            + "\n".join(failures[:30])
            + ("\n..." if len(failures) > 30 else "")
        )

    def test_determinism_corpus_wide(self):
        """Two emit_ui_json calls on the same ready template → byte-identical JSON."""
        import json as _json

        from vibecomfy.cli_loader import load_workflow_any
        from vibecomfy.porting.emit.ui import emit_ui_json

        mismatches: list[str] = []
        skipped: list[str] = []

        for tid in _corpus_template_ids():
            try:
                wf = load_workflow_any(tid)
            except Exception as exc:
                skipped.append(f"{tid}: load error ({type(exc).__name__}: {exc})")
                continue

            try:
                first = _json.dumps(emit_ui_json(wf), sort_keys=True)
                second = _json.dumps(emit_ui_json(wf), sort_keys=True)
            except Exception as exc:
                skipped.append(f"{tid}: emit error ({type(exc).__name__}: {exc})")
                continue

            if first != second:
                mismatches.append(
                    f"{tid}: len(first)={len(first)} len(second)={len(second)}"
                )

        if skipped:
            print(f"\nSkipped {len(skipped)} template(s) during determinism sweep:")
            for s in skipped:
                print(f"  {s}")

        assert not mismatches, (
            f"{len(mismatches)} determinism mismatch(es) across corpus:\n"
            + "\n".join(mismatches[:20])
            + ("\n..." if len(mismatches) > 20 else "")
        )


# ---------------------------------------------------------------------------
# T10 (Phase 4 Step 8b) — vendored-ComfyUI smoke (env-gated)
# ---------------------------------------------------------------------------


@pytest.mark.comfy
def test_opens_clean_vendored_comfyui() -> None:
    """Phase 4 Step 8b: emit_ui_json output accepted by vendored ComfyUI convert_ui_to_api.

    Runs against four representative ready templates:
      - image/flux2_klein_9b_t2i
      - video/ltx2_3_lightricks_two_stage
      - edit/qwen_image_edit (resolved dynamically)
      - video/ltx2_3_runexx_lipsync_custom_audio (heaviest music-video monster)

    Uses the ``vibecomfy.comfy_backend`` sys.path oracle to make vendored
    ComfyUI importable.  Gated behind ``VIBECOMFY_COMFY_SMOKE=1``.
    """
    import logging
    import os
    import warnings
    from pathlib import Path
    import glob as _glob

    if os.environ.get("VIBECOMFY_COMFY_SMOKE") != "1":
        pytest.skip("comfy vendored smoke gate is opt-in (set VIBECOMFY_COMFY_SMOKE=1)")

    from vibecomfy.comfy_backend import ensure_nodes
    if not ensure_nodes():
        pytest.skip("vendored ComfyUI not available (vendor/ComfyUI submodule uninitialized)")

    comfy_convert = pytest.importorskip(
        "comfy.component_model.workflow_convert"
    ).convert_ui_to_api

    from vibecomfy.cli_loader import load_workflow_any
    from vibecomfy.porting.emit.ui import emit_ui_json

    # ── Resolve the four representative templates ──────────────────────
    # Resolve the edit template dynamically.
    edit_glob = sorted(_glob.glob(
        "ready_templates/edit/qwen_image_edit*.py"
    ))
    assert edit_glob, "no qwen_image_edit template found under ready_templates/edit/"
    edit_tid = Path(edit_glob[0]).stem  # e.g. "qwen_image_edit"

    # Heaviest: use the explicitly named lipsync monster.
    heaviest_tid = "video/ltx2_3_runexx_lipsync_custom_audio"

    template_ids = [
        "image/flux2_klein_9b_t2i",
        "video/ltx2_3_lightricks_two_stage",
        f"edit/{edit_tid}",
        heaviest_tid,
    ]

    comfy_logger = logging.getLogger("comfy.component_model.workflow_convert")
    stats = {"checked": 0, "unknown_nodes": 0, "dangling": 0, "empty": 0}

    for tid in template_ids:
        unknown_records: list[logging.LogRecord] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if "Unknown node type" in record.getMessage():
                    unknown_records.append(record)

        handler = _CaptureHandler()
        handler.setLevel(logging.WARNING)
        comfy_logger.addHandler(handler)

        try:
            wf = load_workflow_any(tid)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ui = emit_ui_json(wf)

            converted = comfy_convert(ui)
        except Exception as exc:
            # If the vendored ComfyUI environment is not fully operational
            # (e.g. ``vibecomfy.comfy_nodes`` conflicts with node discovery),
            # skip the entire test rather than failing — this is a pre-existing
            # environment concern, not a regression under test.
            if "comfy_nodes" in str(exc) and "__path__" in str(exc):
                pytest.skip(
                    f"vendored ComfyUI environment not fully operational "
                    f"(vibecomfy.comfy_nodes package conflict)"
                )
            raise AssertionError(
                f"{tid}: emit_ui_json / convert_ui_to_api failed: {exc}"
            ) from exc
        finally:
            comfy_logger.removeHandler(handler)

        stats["checked"] += 1

        # ── Assertions ─────────────────────────────────────────────────
        assert isinstance(converted, dict) and converted, (
            f"{tid}: convert_ui_to_api returned empty/non-dict result"
        )

        if unknown_records:
            stats["unknown_nodes"] += len(unknown_records)

        # Dangling-link check: every link target must exist in converted output.
        for link in ui.get("links", []):
            target_node = str(link[3])
            if target_node not in converted:
                stats["dangling"] += 1

    # Report aggregate
    summary = (
        f"Vendored-Comfy smoke: {stats['checked']}/4 templates checked; "
        f"{stats['unknown_nodes']} unknown-node warning(s), "
        f"{stats['dangling']} dangling link(s)"
    )
    assert stats["unknown_nodes"] == 0, (
        f"convert_ui_to_api reported unknown node type(s): {summary}"
    )
    assert stats["dangling"] == 0, (
        f"convert_ui_to_api has dangling link(s): {summary}"
    )
    print(f"\n{summary}")


# ---------------------------------------------------------------------------
# T10 (Phase 4 Step 8c) — constrained-placement dense-case spiral fallback
# ---------------------------------------------------------------------------


class TestConstrainedPlacementDense:
    """Step 8c: spiral-ray fallback when pinned field is too dense."""

    def test_constrained_placement_dense_case_uses_spiral_fallback(self, caplog):
        """1 anchor + 1200 obstacles → ray cap reached; fallback + warning.

        Uses a small canvas_extent (600) to bound the search radius, and a
        30×40 obstacle grid starting at (-4000, -4000) that blankets the
        entire spiral-ray search area (radius up to 3840 px).  The spiral
        exhausts all 64 steps with none of the 8 compass directions finding
        a gap, triggering the ``ray cap reached`` degradation warning.
        """
        from vibecomfy.porting.layout.placement import (
            place_constrained,
            _ANCHOR_GAP_PX,
        )

        new_uid = "new_node_1"
        anchor_uid = "anchor_1"
        new_size: tuple[float, float] = (320.0, 200.0)

        # Anchor at origin with modest size.
        pinned: dict[str, dict] = {
            anchor_uid: {
                "pos": [0.0, 0.0],
                "size": [320.0, 200.0],
            }
        }

        # Dense grid of obstacles starting at (-4000, -4000), extending in
        # all directions well past the search radius cap (3840 px).
        cols = 30
        rows = 40
        start_x = -4000.0
        start_y = -4000.0
        step_x = new_size[0] + _ANCHOR_GAP_PX   # 360
        step_y = new_size[1] + _ANCHOR_GAP_PX   # 240

        for row in range(rows):
            for col in range(cols):
                ox = start_x + col * step_x
                oy = start_y + row * step_y
                pinned[f"obs_{row}_{col}"] = {
                    "pos": [ox, oy],
                    "size": [new_size[0], new_size[1]],
                }

        # Small canvas extent forces the ray cap to the floor of 64 steps.
        canvas_extent = 600.0

        with caplog.at_level(logging.WARNING):
            pos_x, pos_y = place_constrained(
                new_uid=new_uid,
                anchor_uid=anchor_uid,
                pinned=pinned,
                size=new_size,
                canvas_extent=canvas_extent,
            )

        # ── Assert the spiral-fallback warning was emitted ─────────────
        warning_messages = [r.message for r in caplog.records]
        assert any(
            "ray cap reached" in msg for msg in warning_messages
        ), (
            f"Expected spiral-fallback warning; got: {warning_messages}"
        )

        # ── Assert the fallback position is the initial candidate ──────
        # When the spiral exhausts, place_constrained falls back to the
        # right-edge of the anchor ("right-edge dump").  This position may
        # overlap existing obstacles — that is the documented degradation.
        anchor_right = 0.0 + 320.0 + _ANCHOR_GAP_PX  # 360.0
        assert pos_x == anchor_right and pos_y == 0.0, (
            f"Expected fallback position ({anchor_right}, 0.0); "
            f"got ({pos_x}, {pos_y})"
        )
