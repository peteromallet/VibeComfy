"""Focused unit tests for graph_inspection evidence extraction.

Covers node extraction, widget values, both list-shaped and dict-shaped
ComfyUI link formats, and the text summary builder.
"""

from __future__ import annotations

import pytest

from vibecomfy.executor.graph_inspection import (
    EdgeEvidence,
    GraphDerivations,
    GraphEvidence,
    NodeEvidence,
    SlotEvidence,
    WidgetEvidence,
    _build_text_summary,
    compute_derivations,
    derive_dormant_branches,
    derive_expensive_or_risky,
    derive_inputs,
    derive_model_stack,
    derive_outputs,
    graph_inspection_text,
    inspect_graph,
    normalise_links,
    render_inspect_markdown,
)


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def single_node_graph() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "class_type": "KSampler",
                "widgets_values": [42, 7.5, "euler"],
            },
        ],
    }


@pytest.fixture
def two_node_graph_list_links() -> dict:
    """Graph with list-shaped links (positional format)."""
    return {
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "widgets_values": [20, 7.0, "euler_ancestral"],
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 1},
                    {"name": "positive", "type": "CONDITIONING", "link": None},
                    {"name": "negative", "type": "CONDITIONING", "link": None},
                    {"name": "latent_image", "type": "LATENT", "link": 2},
                ],
            },
        ],
        "links": [
            [1, 1, 0, 2, 0, "MODEL"],
            [2, 3, 0, 2, 3, "LATENT"],
        ],
    }


@pytest.fixture
def two_node_graph_dict_links() -> dict:
    """Graph with dict-shaped links (named format from ComfyUI API)."""
    return {
        "nodes": [
            {"id": 5, "type": "LoadImage", "class_type": "LoadImage", "widgets_values": ["photo.png", "image"]},
            {
                "id": 6,
                "type": "VAEDecode",
                "class_type": "VAEDecode",
                "inputs": [
                    {"name": "samples", "type": "LATENT", "link": 10},
                    {"name": "vae", "type": "VAE", "link": None},
                ],
            },
        ],
        "links": [
            {
                "id": 10,
                "origin_id": 5,
                "origin_slot": 0,
                "target_id": 6,
                "target_slot": 0,
                "type": "LATENT",
            },
        ],
    }


@pytest.fixture
def graph_with_title() -> dict:
    return {
        "nodes": [
            {
                "id": 7,
                "type": "CLIPTextEncode",
                "class_type": "CLIPTextEncode",
                "title": "Positive Prompt",
                "widgets_values": ["a beautiful landscape"],
            },
        ],
    }


@pytest.fixture
def graph_with_outputs() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "class_type": "CheckpointLoaderSimple",
                "outputs": [
                    {"name": "MODEL", "type": "MODEL"},
                    {"name": "CLIP", "type": "CLIP"},
                    {"name": "VAE", "type": "VAE"},
                ],
            },
        ],
        "links": [
            [1, 1, 0, 2, 0, "MODEL"],
        ],
    }


# ── derivation fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def flat_graph() -> dict:
    """Load the flat.json fixture from tests/fixtures/agent_edit/."""
    import json
    from pathlib import Path

    fixture_path = (
        Path(__file__).resolve().parent / "fixtures" / "agent_edit" / "flat.json"
    )
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def disconnected_graph() -> dict:
    """Graph with one output chain (LoadImage → SaveImage) and one dormant
    component (CheckpointLoaderSimple → KSampler) that shares no edges with
    the main chain."""
    return {
        "nodes": [
            # Main output chain
            {"id": 10, "type": "LoadImage", "class_type": "LoadImage",
             "widgets_values": ["input.png", "image"],
             "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1], "slot_index": 0}]},
            {"id": 11, "type": "SaveImage", "class_type": "SaveImage",
             "widgets_values": ["output"],
             "inputs": [{"name": "images", "type": "IMAGE", "link": 1}]},
            # Dormant component (no connection to main chain)
            {"id": 20, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple",
             "widgets_values": ["model.safetensors"],
             "outputs": [
                 {"name": "MODEL", "type": "MODEL", "links": [2], "slot_index": 0},
                 {"name": "CLIP", "type": "CLIP", "links": None, "slot_index": 1},
                 {"name": "VAE", "type": "VAE", "links": None, "slot_index": 2},
             ]},
            {"id": 21, "type": "KSampler", "class_type": "KSampler",
             "widgets_values": [42, 7.5, "euler"],
             "inputs": [
                 {"name": "model", "type": "MODEL", "link": 2},
                 {"name": "positive", "type": "CONDITIONING", "link": None},
                 {"name": "negative", "type": "CONDITIONING", "link": None},
                 {"name": "latent_image", "type": "LATENT", "link": None},
             ]},
        ],
        "links": [
            [1, 10, 0, 11, 0, "IMAGE"],
            [2, 20, 0, 21, 0, "MODEL"],
        ],
    }


@pytest.fixture
def graph_with_expensive_nodes() -> dict:
    """Graph with KSampler (42 steps), Upscale node, and FaceDetailer."""
    return {
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "widgets_values": [12345, 7.0, 42, 8, "euler", "normal", 1.0],
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 1},
                ],
            },
            {"id": 3, "type": "UltimateSDUpscale", "class_type": "UltimateSDUpscale",
             "inputs": [{"name": "image", "type": "IMAGE", "link": 2}]},
            {"id": 4, "type": "FaceDetailer", "class_type": "FaceDetailer",
             "inputs": [{"name": "image", "type": "IMAGE", "link": 3}]},
            {"id": 5, "type": "SaveImage", "class_type": "SaveImage",
             "inputs": [{"name": "images", "type": "IMAGE", "link": 4}]},
        ],
        "links": [
            [1, 1, 0, 2, 0, "MODEL"],
            [2, 2, 0, 3, 0, "IMAGE"],
            [3, 3, 0, 4, 0, "IMAGE"],
            [4, 4, 0, 5, 0, "IMAGE"],
        ],
    }


@pytest.fixture
def graph_no_checkpoint_loader() -> dict:
    """Graph without any CheckpointLoader/UNETLoader — no model stack."""
    return {
        "nodes": [
            {"id": 1, "type": "LoadImage", "class_type": "LoadImage",
             "widgets_values": ["photo.png", "image"]},
            {"id": 2, "type": "SaveImage", "class_type": "SaveImage",
             "inputs": [{"name": "images", "type": "IMAGE", "link": 1}]},
        ],
        "links": [
            [1, 1, 0, 2, 0, "IMAGE"],
        ],
    }


# ── inspect_graph: basic cases ───────────────────────────────────────────────


class TestInspectGraphBasic:
    def test_none_graph_returns_empty_evidence(self) -> None:
        evidence = inspect_graph(None)
        assert evidence.node_count == 0
        assert evidence.nodes == ()
        assert evidence.edges == ()
        assert evidence.summary == ""

    def test_empty_nodes_returns_empty(self) -> None:
        evidence = inspect_graph({"nodes": []})
        assert evidence.node_count == 0
        assert evidence.nodes == ()

    def test_nodes_not_a_list_returns_empty(self) -> None:
        evidence = inspect_graph({"nodes": "not_a_list"})
        assert evidence.node_count == 0

    def test_single_node_extracts_id_and_class_type(self, single_node_graph: dict) -> None:
        evidence = inspect_graph(single_node_graph)
        assert evidence.node_count == 1
        node = evidence.nodes[0]
        assert node.node_id == 1
        assert node.class_type == "KSampler"

    def test_single_node_extracts_widgets(self, single_node_graph: dict) -> None:
        evidence = inspect_graph(single_node_graph)
        node = evidence.nodes[0]
        assert len(node.widgets) == 3
        assert node.widgets[0].index == 0
        assert node.widgets[0].value == 42
        assert node.widgets[1].value == 7.5
        assert node.widgets[2].value == "euler"

    def test_node_title_extracted(self, graph_with_title: dict) -> None:
        evidence = inspect_graph(graph_with_title)
        node = evidence.nodes[0]
        assert node.title == "Positive Prompt"

    def test_node_without_title_has_none_title(self, single_node_graph: dict) -> None:
        evidence = inspect_graph(single_node_graph)
        assert evidence.nodes[0].title is None


# ── link normalisation ───────────────────────────────────────────────────────


class TestNormaliseLinks:
    def test_list_format_links(self) -> None:
        links = [
            [1, 1, 0, 2, 0, "MODEL"],
            [2, 3, 0, 2, 3, "LATENT"],
        ]
        edges = normalise_links(links)
        assert len(edges) == 2

        assert edges[0].link_id == 1
        assert edges[0].origin_node == 1
        assert edges[0].origin_slot == 0
        assert edges[0].target_node == 2
        assert edges[0].target_slot == 0
        assert edges[0].link_type == "MODEL"

        assert edges[1].link_id == 2
        assert edges[1].origin_node == 3
        assert edges[1].origin_slot == 0
        assert edges[1].target_node == 2
        assert edges[1].target_slot == 3
        assert edges[1].link_type == "LATENT"

    def test_dict_format_links(self) -> None:
        links = [
            {
                "id": 10,
                "origin_id": 5,
                "origin_slot": 0,
                "target_id": 6,
                "target_slot": 0,
                "type": "LATENT",
            },
        ]
        edges = normalise_links(links)
        assert len(edges) == 1
        edge = edges[0]
        assert edge.link_id == 10
        assert edge.origin_node == 5
        assert edge.origin_slot == 0
        assert edge.target_node == 6
        assert edge.target_slot == 0
        assert edge.link_type == "LATENT"

    def test_dict_format_uses_link_id_fallback(self) -> None:
        """When 'id' is missing, 'link_id' is used."""
        links = [{"link_id": 99, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0}]
        edges = normalise_links(links)
        assert edges[0].link_id == 99

    def test_mixed_formats_raises_no_error(self) -> None:
        links = [
            [1, 1, 0, 2, 0, "MODEL"],
            {"id": 2, "origin_id": 3, "origin_slot": 0, "target_id": 4, "target_slot": 0, "type": "LATENT"},
        ]
        edges = normalise_links(links)
        assert len(edges) == 2
        assert edges[0].link_id == 1
        assert edges[0].link_type == "MODEL"
        assert edges[1].link_id == 2
        assert edges[1].link_type == "LATENT"

    def test_empty_links_returns_empty_tuple(self) -> None:
        assert normalise_links([]) == ()


# ── input slot extraction ────────────────────────────────────────────────────


class TestInputSlots:
    def test_input_slots_with_links(self, two_node_graph_list_links: dict) -> None:
        evidence = inspect_graph(two_node_graph_list_links)
        # Node 2 (KSampler) has 4 inputs
        node2 = evidence.nodes[1]
        assert node2.node_id == 2
        assert len(node2.input_slots) == 4
        # model slot → linked(1)
        model_slot = node2.input_slots[0]
        assert model_slot.name == "model"
        assert model_slot.slot_type == "input"
        assert model_slot.link_id == 1
        # positive → open
        pos_slot = node2.input_slots[1]
        assert pos_slot.name == "positive"
        assert pos_slot.link_id is None
        # latent_image → linked(2)
        latent_slot = node2.input_slots[3]
        assert latent_slot.name == "latent_image"
        assert latent_slot.link_id == 2

    def test_input_slots_dict_links(self, two_node_graph_dict_links: dict) -> None:
        evidence = inspect_graph(two_node_graph_dict_links)
        # Node 6 (VAEDecode) has 2 inputs
        node6 = evidence.nodes[1]
        assert node6.node_id == 6
        assert len(node6.input_slots) == 2
        assert node6.input_slots[0].name == "samples"
        assert node6.input_slots[0].link_id == 10
        assert node6.input_slots[1].name == "vae"
        assert node6.input_slots[1].link_id is None

    def test_node_without_inputs_has_empty_slots(self, single_node_graph: dict) -> None:
        evidence = inspect_graph(single_node_graph)
        assert evidence.nodes[0].input_slots == ()


# ── output slot extraction ───────────────────────────────────────────────────


class TestOutputSlots:
    def test_output_slots_extracted(self, graph_with_outputs: dict) -> None:
        evidence = inspect_graph(graph_with_outputs)
        node = evidence.nodes[0]
        assert len(node.output_slots) == 3
        assert node.output_slots[0].name == "MODEL"
        assert node.output_slots[1].name == "CLIP"
        assert node.output_slots[2].name == "VAE"
        for slot in node.output_slots:
            assert slot.slot_type == "output"
            assert slot.link_id is None

    def test_node_without_outputs_has_empty_slots(self, single_node_graph: dict) -> None:
        evidence = inspect_graph(single_node_graph)
        assert evidence.nodes[0].output_slots == ()


# ── edge extraction from full graph ──────────────────────────────────────────


class TestEdgeExtraction:
    def test_list_edges_extracted(self, two_node_graph_list_links: dict) -> None:
        evidence = inspect_graph(two_node_graph_list_links)
        assert len(evidence.edges) == 2
        assert evidence.edges[0].link_id == 1
        assert evidence.edges[0].origin_node == 1
        assert evidence.edges[0].target_node == 2
        assert evidence.edges[0].link_type == "MODEL"

    def test_dict_edges_extracted(self, two_node_graph_dict_links: dict) -> None:
        evidence = inspect_graph(two_node_graph_dict_links)
        assert len(evidence.edges) == 1
        edge = evidence.edges[0]
        assert edge.link_id == 10
        assert edge.origin_node == 5
        assert edge.target_node == 6
        assert edge.link_type == "LATENT"


# ── text summary builder ─────────────────────────────────────────────────────


class TestTextSummary:
    def test_text_summary_includes_node_ids_and_types(self, two_node_graph_list_links: dict) -> None:
        evidence = inspect_graph(two_node_graph_list_links)
        summary = evidence.summary
        assert "CheckpointLoaderSimple" in summary
        assert "KSampler" in summary
        assert "[1]" in summary
        assert "[2]" in summary

    def test_text_summary_includes_widget_values(self, single_node_graph: dict) -> None:
        evidence = inspect_graph(single_node_graph)
        summary = evidence.summary
        assert "w0=42" in summary
        assert "w1=7.5" in summary
        assert "w2=euler" in summary

    def test_text_summary_includes_edge_summary(self, two_node_graph_list_links: dict) -> None:
        evidence = inspect_graph(two_node_graph_list_links)
        summary = evidence.summary
        assert "Edges:" in summary
        assert "1 -> 2" in summary
        assert "3 -> 2" in summary

    def test_text_summary_includes_input_slot_status(self, two_node_graph_list_links: dict) -> None:
        evidence = inspect_graph(two_node_graph_list_links)
        summary = evidence.summary
        assert "model=linked(1)" in summary
        assert "positive=open" in summary

    def test_empty_graph_summary(self) -> None:
        empty = GraphEvidence(node_count=0)
        assert _build_text_summary(empty) == "Empty graph (0 nodes)."

    def test_node_title_in_summary(self, graph_with_title: dict) -> None:
        evidence = inspect_graph(graph_with_title)
        summary = evidence.summary
        assert '("Positive Prompt")' in summary


# ── graph_inspection_text convenience ────────────────────────────────────────


class TestGraphInspectionText:
    def test_returns_none_for_none_graph(self) -> None:
        assert graph_inspection_text(None) is None

    def test_returns_none_for_empty_graph(self) -> None:
        assert graph_inspection_text({"nodes": []}) is None

    def test_returns_string_for_valid_graph(self, single_node_graph: dict) -> None:
        text = graph_inspection_text(single_node_graph)
        assert isinstance(text, str)
        assert "KSampler" in text


# ── WidgetEvidence contract ──────────────────────────────────────────────────


class TestWidgetEvidenceContract:
    def test_widget_evidence_construction(self) -> None:
        w = WidgetEvidence(index=0, value=42, name="seed")
        assert w.index == 0
        assert w.value == 42
        assert w.name == "seed"

    def test_widget_evidence_default_name(self) -> None:
        w = WidgetEvidence(index=3, value="euler")
        assert w.name is None

    def test_truncated_widgets_in_summary(self) -> None:
        """More than 5 widgets: only first 5 appear in text summary."""
        graph = {
            "nodes": [{
                "id": 1, "type": "TestNode", "class_type": "TestNode",
                "widgets_values": [1, 2, 3, 4, 5, 6, 7],
            }],
        }
        evidence = inspect_graph(graph)
        evidence_node = evidence.nodes[0]
        # All 7 widgets should be in structured evidence
        assert len(evidence_node.widgets) == 7
        # But only 5 in the text summary
        assert "w4=5" in evidence.summary
        assert "w5=6" not in evidence.summary


# ── _graph_inspection alias ──────────────────────────────────────────────────


class TestGraphInspectionAlias:
    def test_alias_is_callable(self, single_node_graph: dict) -> None:
        from vibecomfy.executor.graph_inspection import _graph_inspection
        result = _graph_inspection(single_node_graph)
        assert isinstance(result, str)
        assert "KSampler" in result

    def test_alias_returns_none_for_none(self) -> None:
        from vibecomfy.executor.graph_inspection import _graph_inspection
        assert _graph_inspection(None) is None


# ── derive_inputs ─────────────────────────────────────────────────────────────


class TestDeriveInputs:
    def test_inputs_from_flat_fixture(self, flat_graph: dict) -> None:
        """flat.json: nodes 1 (CheckpointLoaderSimple) and 4 (EmptyLatentImage)
        have no linked inputs; all other nodes have at least one linked input."""
        evidence = inspect_graph(flat_graph)
        inputs = derive_inputs(evidence)
        assert set(inputs) == {1, 4}

    def test_inputs_two_node_list(self, two_node_graph_list_links: dict) -> None:
        """Node 1 (CheckpointLoaderSimple) has no inputs → input.
        Node 2 (KSampler) has linked inputs → not an input."""
        evidence = inspect_graph(two_node_graph_list_links)
        inputs = derive_inputs(evidence)
        assert inputs == (1,)

    def test_inputs_dict_links(self, two_node_graph_dict_links: dict) -> None:
        """Node 5 (LoadImage) has no linked inputs → input.
        Node 6 (VAEDecode) has a linked input → not an input."""
        evidence = inspect_graph(two_node_graph_dict_links)
        inputs = derive_inputs(evidence)
        assert inputs == (5,)

    def test_inputs_expensive_graph(self, graph_with_expensive_nodes: dict) -> None:
        """Only CheckpointLoaderSimple should have no incoming links."""
        evidence = inspect_graph(graph_with_expensive_nodes)
        inputs = derive_inputs(evidence)
        assert inputs == (1,)

    def test_inputs_disconnected_graph(self, disconnected_graph: dict) -> None:
        """Main chain: LoadImage (10) → SaveImage (11).
        Dormant: CheckpointLoaderSimple (20) → KSampler (21).
        Inputs are 10 and 20 (no linked inputs on either)."""
        evidence = inspect_graph(disconnected_graph)
        inputs = derive_inputs(evidence)
        assert set(inputs) == {10, 20}

    def test_no_inputs_empty_graph(self) -> None:
        evidence = inspect_graph({"nodes": []})
        assert derive_inputs(evidence) == ()

    def test_single_node_no_inputs_is_input(self, single_node_graph: dict) -> None:
        evidence = inspect_graph(single_node_graph)
        assert derive_inputs(evidence) == (1,)


# ── derive_outputs ────────────────────────────────────────────────────────────


class TestDeriveOutputs:
    def test_outputs_from_flat_fixture(self, flat_graph: dict) -> None:
        """flat.json: only node 7 (SaveImage) has no outgoing edges."""
        evidence = inspect_graph(flat_graph)
        outputs = derive_outputs(evidence)
        assert outputs == (7,)

    def test_outputs_two_node_list(self, two_node_graph_list_links: dict) -> None:
        """Node 1 → Node 2.  Node 2 has no outgoing edges."""
        evidence = inspect_graph(two_node_graph_list_links)
        outputs = derive_outputs(evidence)
        assert outputs == (2,)

    def test_outputs_dict_links(self, two_node_graph_dict_links: dict) -> None:
        """Node 5 → Node 6.  Node 6 has no outgoing edges."""
        evidence = inspect_graph(two_node_graph_dict_links)
        outputs = derive_outputs(evidence)
        assert outputs == (6,)

    def test_outputs_expensive_graph(self, graph_with_expensive_nodes: dict) -> None:
        """SaveImage (5) has no outgoing edges."""
        evidence = inspect_graph(graph_with_expensive_nodes)
        outputs = derive_outputs(evidence)
        assert outputs == (5,)

    def test_outputs_disconnected_graph(self, disconnected_graph: dict) -> None:
        """Outputs across both components: SaveImage (11) and KSampler (21)."""
        evidence = inspect_graph(disconnected_graph)
        outputs = derive_outputs(evidence)
        assert set(outputs) == {11, 21}

    def test_no_outputs_empty_graph(self) -> None:
        evidence = inspect_graph({"nodes": []})
        assert derive_outputs(evidence) == ()

    def test_single_node_no_edges_is_output(self, single_node_graph: dict) -> None:
        evidence = inspect_graph(single_node_graph)
        assert derive_outputs(evidence) == (1,)


# ── derive_model_stack ────────────────────────────────────────────────────────


class TestDeriveModelStack:
    def test_model_stack_from_flat_fixture(self, flat_graph: dict) -> None:
        """CheckpointLoaderSimple (1) → KSampler (5) → VAEDecode (6) → SaveImage (7).
        All reachable from the CheckpointLoader."""
        evidence = inspect_graph(flat_graph)
        stack = derive_model_stack(evidence)
        # BFS from node 1 should visit 1, then its targets in edge order
        assert 1 in stack
        assert 5 in stack
        assert 6 in stack
        assert 7 in stack
        # Node 1 should be first (the seed)
        assert stack[0] == 1

    def test_model_stack_two_node_list(self, two_node_graph_list_links: dict) -> None:
        """CheckpointLoaderSimple (1) → KSampler (2)."""
        evidence = inspect_graph(two_node_graph_list_links)
        stack = derive_model_stack(evidence)
        assert set(stack) == {1, 2}
        assert stack[0] == 1

    def test_no_model_stack_without_checkpoint_loader(
        self, graph_no_checkpoint_loader: dict
    ) -> None:
        """LoadImage → SaveImage: no CheckpointLoader → empty model_stack."""
        evidence = inspect_graph(graph_no_checkpoint_loader)
        stack = derive_model_stack(evidence)
        assert stack == ()

    def test_no_model_stack_empty_graph(self) -> None:
        evidence = inspect_graph({"nodes": []})
        assert derive_model_stack(evidence) == ()

    def test_model_stack_disconnected_graph(self, disconnected_graph: dict) -> None:
        """Only the dormant CheckpointLoaderSimple (20) seeds the model stack.
        KSampler (21) is reachable from it.  Main chain (10, 11) is not
        reachable from any CheckpointLoader."""
        evidence = inspect_graph(disconnected_graph)
        stack = derive_model_stack(evidence)
        assert set(stack) == {20, 21}
        assert stack[0] == 20

    def test_model_stack_includes_unetloader(self) -> None:
        """UNETLoader should also seed the model stack."""
        graph = {
            "nodes": [
                {"id": 1, "type": "UNETLoader", "class_type": "UNETLoader"},
                {"id": 2, "type": "KSampler", "class_type": "KSampler",
                 "inputs": [{"name": "model", "type": "MODEL", "link": 1}]},
            ],
            "links": [[1, 1, 0, 2, 0, "MODEL"]],
        }
        evidence = inspect_graph(graph)
        stack = derive_model_stack(evidence)
        assert set(stack) == {1, 2}


# ── derive_dormant_branches ───────────────────────────────────────────────────


class TestDeriveDormantBranches:
    def test_no_dormant_branches_flat_fixture(self, flat_graph: dict) -> None:
        """flat.json: all nodes are reachable from inputs."""
        evidence = inspect_graph(flat_graph)
        dormant = derive_dormant_branches(evidence)
        assert dormant == ()

    def test_dormant_branches_disconnected_graph(self, disconnected_graph: dict) -> None:
        """Main chain (10→11) is reachable from input 10.
        Dormant component (20→21) is NOT reachable from input 10.
        So dormant = [(20, 21)]."""
        evidence = inspect_graph(disconnected_graph)
        dormant = derive_dormant_branches(evidence)
        assert len(dormant) == 1
        assert dormant[0] == (20, 21)

    def test_dormant_branches_multiple_disconnected(self) -> None:
        """Three isolated nodes with no edges between any of them.
        None contain a terminal output, so no component provides a main
        output chain — dormant detection returns empty (graph is incomplete,
        not dormant)."""
        graph = {
            "nodes": [
                {"id": 1, "type": "LoadImage", "class_type": "LoadImage"},
                {"id": 2, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
                {"id": 3, "type": "KSampler", "class_type": "KSampler"},
            ],
        }
        evidence = inspect_graph(graph)
        dormant = derive_dormant_branches(evidence)
        # No terminal output anywhere → nothing flagged as dormant
        assert dormant == ()

    def test_dormant_branches_without_any_inputs(self) -> None:
        """Graph where every node has a linked input (no inputs at all).
        The single connected component contains SaveImage → not dormant."""
        graph = {
            "nodes": [
                {"id": 1, "type": "LoadImage", "class_type": "LoadImage",
                 "inputs": [{"name": "image", "type": "IMAGE", "link": 99}]},
                {"id": 2, "type": "SaveImage", "class_type": "SaveImage",
                 "inputs": [{"name": "images", "type": "IMAGE", "link": 99}]},
            ],
            "links": [[99, 1, 0, 2, 0, "IMAGE"]],
        }
        evidence = inspect_graph(graph)
        # Single component contains SaveImage → not dormant
        dormant = derive_dormant_branches(evidence)
        assert dormant == ()

    def test_no_dormant_empty_graph(self) -> None:
        evidence = inspect_graph({"nodes": []})
        assert derive_dormant_branches(evidence) == ()

    def test_dormant_single_isolated_node(self) -> None:
        """One node reachable from input, one isolated node."""
        graph = {
            "nodes": [
                {"id": 1, "type": "LoadImage", "class_type": "LoadImage"},
                {"id": 2, "type": "SaveImage", "class_type": "SaveImage",
                 "inputs": [{"name": "images", "type": "IMAGE", "link": 1}]},
                {"id": 99, "type": "KSampler", "class_type": "KSampler"},  # isolated
            ],
            "links": [[1, 1, 0, 2, 0, "IMAGE"]],
        }
        evidence = inspect_graph(graph)
        dormant = derive_dormant_branches(evidence)
        assert len(dormant) == 1
        assert dormant[0] == (99,)


# ── derive_expensive_or_risky ─────────────────────────────────────────────────


class TestDeriveExpensiveOrRisky:
    def test_expensive_ksampler_high_steps(self, graph_with_expensive_nodes: dict) -> None:
        """KSampler with 42 steps (>30) should be flagged."""
        evidence = inspect_graph(graph_with_expensive_nodes)
        flagged = derive_expensive_or_risky(evidence)
        flagged_ids = {nid for nid, _ in flagged}
        assert 2 in flagged_ids  # KSampler
        # Check the reason mentions steps
        ksampler_reason = [r for nid, r in flagged if nid == 2][0]
        assert "42" in ksampler_reason

    def test_expensive_upscale_detected(self, graph_with_expensive_nodes: dict) -> None:
        evidence = inspect_graph(graph_with_expensive_nodes)
        flagged = derive_expensive_or_risky(evidence)
        flagged_ids = {nid for nid, _ in flagged}
        assert 3 in flagged_ids  # UltimateSDUpscale
        upscale_reason = [r for nid, r in flagged if nid == 3][0]
        assert "upscale" in upscale_reason.lower()

    def test_expensive_facedetailer_detected(self, graph_with_expensive_nodes: dict) -> None:
        evidence = inspect_graph(graph_with_expensive_nodes)
        flagged = derive_expensive_or_risky(evidence)
        flagged_ids = {nid for nid, _ in flagged}
        assert 4 in flagged_ids  # FaceDetailer

    def test_ksampler_low_steps_not_flagged_high(self) -> None:
        """KSampler with ≤30 steps should not get a steps warning, just 'core sampling step'."""
        graph = {
            "nodes": [
                {"id": 1, "type": "KSampler", "class_type": "KSampler",
                 "widgets_values": [42, 7.5, 20]},
            ],
        }
        evidence = inspect_graph(graph)
        flagged = derive_expensive_or_risky(evidence)
        assert len(flagged) == 1
        assert flagged[0][0] == 1
        assert "core sampling step" in flagged[0][1]
        assert "steps" not in flagged[0][1]

    def test_no_expensive_in_simple_graph(self, two_node_graph_dict_links: dict) -> None:
        """LoadImage + VAEDecode: neither matches expensive patterns."""
        evidence = inspect_graph(two_node_graph_dict_links)
        flagged = derive_expensive_or_risky(evidence)
        assert flagged == ()

    def test_no_expensive_empty_graph(self) -> None:
        evidence = inspect_graph({"nodes": []})
        assert derive_expensive_or_risky(evidence) == ()

    def test_hdr_detected(self) -> None:
        graph = {
            "nodes": [
                {"id": 1, "type": "HDRSampler", "class_type": "HDRSampler"},
            ],
        }
        evidence = inspect_graph(graph)
        flagged = derive_expensive_or_risky(evidence)
        assert len(flagged) == 1
        assert "HDR" in flagged[0][1]

    def test_batch_detected(self) -> None:
        graph = {
            "nodes": [
                {"id": 1, "type": "BatchProcess", "class_type": "BatchProcess"},
            ],
        }
        evidence = inspect_graph(graph)
        flagged = derive_expensive_or_risky(evidence)
        assert len(flagged) == 1
        assert "batch" in flagged[0][1].lower()


# ── compute_derivations (integration) ─────────────────────────────────────────


class TestComputeDerivations:
    def test_compute_on_flat_fixture(self, flat_graph: dict) -> None:
        evidence = inspect_graph(flat_graph)
        d = compute_derivations(evidence)
        assert isinstance(d, GraphDerivations)
        assert set(d.inputs) == {1, 4}
        assert d.outputs == (7,)
        assert 1 in d.model_stack
        assert 5 in d.model_stack
        assert d.dormant_branches == ()
        # KSampler (5) has 7 widgets, widget[2] = 20 → not >30 → "core sampling step"
        assert len(d.expensive_or_risky) >= 1
        ksampler_flags = [r for nid, r in d.expensive_or_risky if nid == 5]
        assert len(ksampler_flags) == 1

    def test_compute_on_disconnected_graph(self, disconnected_graph: dict) -> None:
        evidence = inspect_graph(disconnected_graph)
        d = compute_derivations(evidence)
        assert set(d.inputs) == {10, 20}
        assert set(d.outputs) == {11, 21}
        assert set(d.model_stack) == {20, 21}
        assert len(d.dormant_branches) == 1
        assert d.dormant_branches[0] == (20, 21)
        # KSampler (21) has 3 widgets, widget[2]="euler" (not int/float) → "core sampling step"
        ksampler_flags = [r for nid, r in d.expensive_or_risky if nid == 21]
        assert len(ksampler_flags) == 1

    def test_compute_on_expensive_graph(self, graph_with_expensive_nodes: dict) -> None:
        evidence = inspect_graph(graph_with_expensive_nodes)
        d = compute_derivations(evidence)
        flagged_ids = {nid for nid, _ in d.expensive_or_risky}
        assert flagged_ids == {2, 3, 4}

    def test_compute_on_empty_graph(self) -> None:
        evidence = inspect_graph({"nodes": []})
        d = compute_derivations(evidence)
        assert d.inputs == ()
        assert d.outputs == ()
        assert d.model_stack == ()
        assert d.dormant_branches == ()
        assert d.expensive_or_risky == ()

    def test_derivations_dataclass_is_frozen(self) -> None:
        d = GraphDerivations(inputs=(1, 2), outputs=(3,))
        with pytest.raises(Exception):
            d.inputs = (4,)  # type: ignore[misc]


# ── render_inspect_markdown tests ─────────────────────────────────────────────


class TestRenderInspectMarkdown:
    """Tests for the deterministic inspect Markdown renderer."""

    # ── empty / trivial graphs ─────────────────────────────────────

    def test_empty_graph_returns_overview_only(self) -> None:
        """Empty graph → only ## Overview with empty message."""
        evidence = inspect_graph({"nodes": []})
        md = render_inspect_markdown(evidence)
        assert md == "## Overview\nEmpty graph (0 nodes).\n"

    def test_none_graph_returns_overview_only(self) -> None:
        """None graph → only ## Overview with empty message."""
        evidence = inspect_graph(None)
        md = render_inspect_markdown(evidence)
        assert md == "## Overview\nEmpty graph (0 nodes).\n"

    # ── required headings ──────────────────────────────────────────

    REQUIRED_HEADINGS = [
        "## Overview",
        "## Stages / Data Flow",
        "## Model Stack",
        "## Key Nodes",
        "## Inputs / Outputs",
        "## Dormant Branches",
        "## Expensive / Risky Areas",
    ]

    def test_all_required_headings_present_single_node(
        self, single_node_graph: dict
    ) -> None:
        """All seven stable headings appear for a single-node graph."""
        evidence = inspect_graph(single_node_graph)
        md = render_inspect_markdown(evidence)
        for heading in self.REQUIRED_HEADINGS:
            assert heading in md, f"Missing heading: {heading}"

    def test_all_required_headings_present_multi_node(
        self, two_node_graph_list_links: dict
    ) -> None:
        """All seven stable headings appear for a multi-node graph."""
        evidence = inspect_graph(two_node_graph_list_links)
        md = render_inspect_markdown(evidence)
        for heading in self.REQUIRED_HEADINGS:
            assert heading in md, f"Missing heading: {heading}"

    def test_all_required_headings_present_flat_fixture(
        self, flat_graph: dict
    ) -> None:
        """All seven stable headings appear for the flat.json fixture."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        for heading in self.REQUIRED_HEADINGS:
            assert heading in md, f"Missing heading: {heading}"

    # ── overview section ───────────────────────────────────────────

    def test_overview_includes_node_and_edge_count(
        self, two_node_graph_list_links: dict
    ) -> None:
        """Overview contains node count and edge count."""
        evidence = inspect_graph(two_node_graph_list_links)
        md = render_inspect_markdown(evidence)
        assert "2 node(s)" in md
        assert "2 edge(s)" in md

    def test_overview_includes_class_type_census(self, flat_graph: dict) -> None:
        """Overview includes a census of class types."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        assert "Class types:" in md
        # flat.json has these class types
        assert "CheckpointLoaderSimple" in md
        assert "KSampler" in md
        assert "VAEDecode" in md
        assert "SaveImage" in md

    # ── key nodes: node names and class types ──────────────────────

    def test_key_nodes_includes_node_bold_labels(
        self, two_node_graph_list_links: dict
    ) -> None:
        """Key Nodes section lists each node with **[id] ClassType**."""
        evidence = inspect_graph(two_node_graph_list_links)
        md = render_inspect_markdown(evidence)
        assert "**[1] CheckpointLoaderSimple**" in md
        assert "**[2] KSampler**" in md

    def test_key_nodes_includes_title_when_present(
        self, graph_with_title: dict
    ) -> None:
        """Key Nodes includes the title in bold label when present."""
        evidence = inspect_graph(graph_with_title)
        md = render_inspect_markdown(evidence)
        assert "**[7] CLIPTextEncode (Positive Prompt)**" in md

    def test_key_nodes_includes_node_ids_from_flat_fixture(
        self, flat_graph: dict
    ) -> None:
        """Key Nodes lists each node from the flat.json fixture."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        for node in evidence.nodes:
            assert f"[{node.node_id}]" in md
            assert node.class_type in md

    # ── key nodes: widget values ───────────────────────────────────

    def test_key_nodes_shows_widget_values(
        self, single_node_graph: dict
    ) -> None:
        """Widget values are rendered under each node."""
        evidence = inspect_graph(single_node_graph)
        md = render_inspect_markdown(evidence)
        assert "Widgets:" in md
        assert "w[0]=42" in md
        assert "w[1]=7.5" in md
        assert "w[2]=euler" in md

    def test_key_nodes_widget_values_from_flat_fixture(
        self, flat_graph: dict
    ) -> None:
        """Widget values from flat.json appear in Key Nodes."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        # CheckpointLoaderSimple has one widget (ckpt_name)
        assert "v1-5-pruned-emaonly.ckpt" in md
        # KSampler has seed=42, steps=20, cfg=7.5, etc.
        assert "w[0]=42" in md
        assert "w[2]=20" in md  # widget index 2 is steps

    def test_key_nodes_shows_widgets_none_for_no_widgets(self) -> None:
        """Node with no widgets shows 'Widgets: none'."""
        graph = {
            "nodes": [{"id": 99, "type": "Note", "class_type": "Note"}],
        }
        evidence = inspect_graph(graph)
        md = render_inspect_markdown(evidence)
        assert "Widgets: none" in md

    # ── key nodes: slot wiring ─────────────────────────────────────

    def test_key_nodes_shows_input_slots_linked_and_open(
        self, two_node_graph_list_links: dict
    ) -> None:
        """Input slots show linked(id) or open status."""
        evidence = inspect_graph(two_node_graph_list_links)
        md = render_inspect_markdown(evidence)
        assert "model=linked(1)" in md
        assert "positive=open" in md
        assert "negative=open" in md
        assert "latent_image=linked(2)" in md

    def test_key_nodes_shows_output_slots(
        self, graph_with_outputs: dict
    ) -> None:
        """Output slots are listed for nodes that have them."""
        evidence = inspect_graph(graph_with_outputs)
        md = render_inspect_markdown(evidence)
        assert "Output slots:" in md
        assert "MODEL" in md
        assert "CLIP" in md
        assert "VAE" in md

    def test_key_nodes_shows_input_slots_none_when_empty(
        self, single_node_graph: dict
    ) -> None:
        """Node with no input slots shows 'Input slots: none'."""
        evidence = inspect_graph(single_node_graph)
        md = render_inspect_markdown(evidence)
        assert "Input slots: none" in md

    def test_key_nodes_shows_output_slots_none_when_empty(
        self, single_node_graph: dict
    ) -> None:
        """Node with no output slots shows 'Output slots: none'."""
        evidence = inspect_graph(single_node_graph)
        md = render_inspect_markdown(evidence)
        assert "Output slots: none" in md

    # ── data-flow facts ────────────────────────────────────────────

    def test_data_flow_shows_inputs_and_outputs(
        self, two_node_graph_list_links: dict
    ) -> None:
        """Stages / Data Flow shows inputs, outputs, and edges."""
        evidence = inspect_graph(two_node_graph_list_links)
        md = render_inspect_markdown(evidence)
        assert "**Inputs:**" in md
        assert "[1] CheckpointLoaderSimple" in md
        assert "**Outputs:**" in md
        assert "[2] KSampler" in md
        assert "**Data-flow edges:**" in md
        assert "[1] CheckpointLoaderSimple → [2] KSampler (MODEL)" in md

    def test_data_flow_single_node_no_edges(
        self, single_node_graph: dict
    ) -> None:
        """Single node with no edges states no data flow."""
        evidence = inspect_graph(single_node_graph)
        md = render_inspect_markdown(evidence)
        assert "Single node with no edges" in md

    def test_data_flow_from_flat_fixture(
        self, flat_graph: dict
    ) -> None:
        """Data flow section shows the key connections from flat.json."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        assert "**Inputs:**" in md
        assert "**Outputs:**" in md
        assert "**Data-flow edges:**" in md
        # Key connections
        assert "CheckpointLoaderSimple" in md
        assert "SaveImage" in md

    # ── model-stack facts ──────────────────────────────────────────

    def test_model_stack_shows_chain(
        self, two_node_graph_list_links: dict
    ) -> None:
        """Model Stack lists the checkpoint loader and its reachable nodes."""
        evidence = inspect_graph(two_node_graph_list_links)
        md = render_inspect_markdown(evidence)
        assert "[1] CheckpointLoaderSimple" in md
        assert "[2] KSampler" in md

    def test_model_stack_none_detected_when_empty(self) -> None:
        """Model Stack shows 'None detected' when no checkpoint loader."""
        graph = {
            "nodes": [
                {"id": 1, "type": "LoadImage", "class_type": "LoadImage"},
                {"id": 2, "type": "SaveImage", "class_type": "SaveImage",
                 "inputs": [{"name": "images", "type": "IMAGE", "link": 1}]},
            ],
            "links": [[1, 1, 0, 2, 0, "IMAGE"]],
        }
        evidence = inspect_graph(graph)
        md = render_inspect_markdown(evidence)
        # The heading exists, but content says None detected
        assert "## Model Stack\nNone detected" in md

    def test_model_stack_from_flat_fixture(
        self, flat_graph: dict
    ) -> None:
        """Model Stack from flat.json includes the checkpoint loader chain."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        assert "The following nodes participate in the model-loading chain" in md
        assert "[1] CheckpointLoaderSimple" in md
        assert "[5] KSampler" in md
        assert "[6] VAEDecode" in md
        assert "[7] SaveImage" in md

    # ── empty optional sections → "None detected" ──────────────────

    def test_empty_model_stack_is_none_detected(
        self, single_node_graph: dict
    ) -> None:
        """Single KSampler with no checkpoint loader → Model Stack: None detected."""
        evidence = inspect_graph(single_node_graph)
        md = render_inspect_markdown(evidence)
        assert "## Model Stack\nNone detected" in md

    def test_empty_dormant_branches_is_none_detected(
        self, two_node_graph_list_links: dict
    ) -> None:
        """Connected graph → Dormant Branches: None detected."""
        evidence = inspect_graph(two_node_graph_list_links)
        md = render_inspect_markdown(evidence)
        assert "## Dormant Branches\nNone detected" in md

    def test_empty_expensive_risky_is_none_detected(
        self, two_node_graph_dict_links: dict
    ) -> None:
        """LoadImage + VAEDecode → Expensive: None detected."""
        evidence = inspect_graph(two_node_graph_dict_links)
        md = render_inspect_markdown(evidence)
        assert "## Expensive / Risky Areas\nNone detected" in md

    # ── dormant branches section ───────────────────────────────────

    def test_dormant_branches_rendered(
        self, disconnected_graph: dict
    ) -> None:
        """Dormant Branches lists disconnected components."""
        evidence = inspect_graph(disconnected_graph)
        md = render_inspect_markdown(evidence)
        assert "The following" in md
        assert "disconnected component" in md
        assert "Branch 1:" in md
        assert "[20] CheckpointLoaderSimple" in md
        assert "[21] KSampler" in md

    # ── expensive / risky section ──────────────────────────────────

    def test_expensive_risky_rendered(
        self, graph_with_expensive_nodes: dict
    ) -> None:
        """Expensive / Risky lists flagged nodes with reasons."""
        evidence = inspect_graph(graph_with_expensive_nodes)
        md = render_inspect_markdown(evidence)
        assert "[2] KSampler:" in md
        assert "42" in md or "sampling" in md
        assert "[3] UltimateSDUpscale:" in md
        assert "[4] FaceDetailer:" in md

    # ── no repair / Apply / Reject wording ─────────────────────────

    def test_no_repair_wording(self, flat_graph: dict) -> None:
        """Markdown contains no repair suggestions."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        assert "repair" not in md.lower()
        assert "should fix" not in md.lower()
        assert "needs fixing" not in md.lower()
        assert "recommendation" not in md.lower()

    def test_no_apply_reject_wording(self, flat_graph: dict) -> None:
        """Markdown contains no Apply/Reject guidance."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        assert "apply" not in md.lower()
        assert "reject" not in md.lower()
        assert "accept changes" not in md.lower()

    def test_no_external_model_claims(self, flat_graph: dict) -> None:
        """Markdown contains no external model-family claims."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        assert "stable diffusion" not in md.lower()
        assert "sdxl" not in md.lower()
        assert "flux" not in md.lower()

    # ── integration with derivations ──────────────────────────────

    def test_with_precomputed_derivations(
        self, flat_graph: dict
    ) -> None:
        """Renderer accepts and uses pre-computed derivations."""
        evidence = inspect_graph(flat_graph)
        derivations = compute_derivations(evidence)
        md = render_inspect_markdown(evidence, derivations=derivations)
        assert "## Overview" in md
        assert "## Key Nodes" in md

    def test_derivations_computed_automatically(
        self, flat_graph: dict
    ) -> None:
        """Renderer auto-computes derivations when not provided."""
        evidence = inspect_graph(flat_graph)
        md1 = render_inspect_markdown(evidence)
        derivations = compute_derivations(evidence)
        md2 = render_inspect_markdown(evidence, derivations=derivations)
        # Both paths should produce identical output
        assert md1 == md2

    # ── determinism ────────────────────────────────────────────────

    def test_deterministic_output(
        self, flat_graph: dict
    ) -> None:
        """Multiple calls produce identical output."""
        evidence = inspect_graph(flat_graph)
        md1 = render_inspect_markdown(evidence)
        md2 = render_inspect_markdown(evidence)
        md3 = render_inspect_markdown(evidence)
        assert md1 == md2 == md3

    def test_deterministic_output_disconnected(
        self, disconnected_graph: dict
    ) -> None:
        """Deterministic output for disconnected graphs."""
        evidence = inspect_graph(disconnected_graph)
        md1 = render_inspect_markdown(evidence)
        md2 = render_inspect_markdown(evidence)
        assert md1 == md2

    # ── inputs/outputs section details ────────────────────────────

    def test_inputs_outputs_lists_input_nodes(
        self, flat_graph: dict
    ) -> None:
        """Inputs / Outputs section lists each input node."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        assert "**Inputs (2):**" in md
        assert "[1] CheckpointLoaderSimple" in md
        assert "[4] EmptyLatentImage" in md

    def test_inputs_outputs_lists_output_nodes(
        self, flat_graph: dict
    ) -> None:
        """Inputs / Outputs section lists each output node."""
        evidence = inspect_graph(flat_graph)
        md = render_inspect_markdown(evidence)
        assert "**Outputs (1):**" in md
        assert "[7] SaveImage" in md
