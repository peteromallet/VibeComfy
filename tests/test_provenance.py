from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.executor.provenance import collect_type_instances, load_source_workflow

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_FIXTURE = (
    _REPO_ROOT
    / "ready_templates"
    / "sources"
    / "official"
    / "edit"
    / "flux2_klein_4b_image_edit_base.json"
)


def _make_vibecomfy_extra(
    *,
    source_template: str | None = None,
    prior_path: str | None = None,
) -> dict:
    vibecomfy: dict = {"layout_version": 1}
    if source_template is not None:
        vibecomfy["source_template"] = source_template
    if prior_path is not None:
        vibecomfy["prior_path"] = prior_path
    return {"extra": {"vibecomfy": vibecomfy}}


class TestLoadSourceWorkflow:
    """``load_source_workflow`` resolution tests."""

    def test_python_prior_path_falls_back_to_api_source_workflow(self) -> None:
        """A production-shape .py prior_path loads its API source JSON."""
        prior_path = (
            Path(__file__).resolve().parents[1]
            / "ready_templates"
            / "image"
            / "flux2_klein_4b_t2i.py"
        )
        graph = _make_vibecomfy_extra(
            source_template="image/flux2_klein_4b_t2i",
            prior_path=str(prior_path),
        )

        result = load_source_workflow(graph)

        assert result is not None
        assert isinstance(result, dict)
        assert isinstance(result.get("nodes"), (dict, list))

    def test_hand_built_python_prior_path_returns_none(self) -> None:
        """A hand-built .py template without API source JSON fails gracefully."""
        prior_path = (
            Path(__file__).resolve().parents[1]
            / "ready_templates"
            / "image"
            / "basic_image_upscale.py"
        )
        graph = _make_vibecomfy_extra(
            source_template="image/basic_image_upscale",
            prior_path=str(prior_path),
        )

        assert load_source_workflow(graph) is None

    def test_valid_prior_path_loads_source_workflow(self) -> None:
        """(a) A graph with a valid prior_path returns the source dict."""
        graph = _make_vibecomfy_extra(prior_path=str(_SOURCE_FIXTURE))
        result = load_source_workflow(graph)

        assert result is not None
        assert isinstance(result, dict)
        nodes = result.get("nodes")
        assert isinstance(nodes, dict)
        # At least one known node type in this fixture
        node_types = {
            n.get("type")
            for n in nodes.values()
            if isinstance(n, dict) and n.get("type")
        }
        assert "LoadImage" in node_types
        assert "SaveImage" in node_types

    def test_missing_prior_path_and_no_template_returns_none(self) -> None:
        """(b) Missing prior_path + absent source_template → None, no raise."""
        # Stale/invalid prior_path
        graph = _make_vibecomfy_extra(prior_path="/nonexistent/deadbeef.json")
        result = load_source_workflow(graph)
        assert result is None

    def test_no_breadcrumb_returns_none(self) -> None:
        """No extra.vibecomfy at all → None."""
        result = load_source_workflow({})
        assert result is None

    def test_no_extra_at_all_returns_none(self) -> None:
        result = load_source_workflow({"nodes": []})
        assert result is None


class TestCollectTypeInstances:
    """``collect_type_instances`` tests."""

    def test_litegraph_list_link_preserves_incident_edge(self) -> None:
        source = {
            "nodes": {
                "10": {
                    "id": 10,
                    "type": "LoadImage",
                    "inputs": [],
                    "outputs": [
                        {"name": "IMAGE", "type": "IMAGE", "links": [1]},
                    ],
                    "widgets_values": ["cat.png", "image"],
                },
                "20": {
                    "id": 20,
                    "type": "SaveImage",
                    "inputs": [
                        {"name": "images", "type": "IMAGE", "link": 1},
                    ],
                    "outputs": [],
                    "widgets_values": ["output_prefix"],
                },
            },
            "links": [[1, 10, 0, 20, 0, "IMAGE"]],
        }

        results = collect_type_instances(source, "SaveImage")

        assert len(results) == 1
        incident_edges = results[0]["incident_edges"]
        assert incident_edges
        assert incident_edges[0] == {
            "peer_class": "LoadImage",
            "socket": "images",
            "direction": "in",
        }

    def test_two_same_type_nodes_returned_with_distinct_values(self) -> None:
        """(c) Source workflow with two nodes of same class_type →
        returns BOTH with distinct widget_values."""
        source = {
            "nodes": [
                {
                    "id": 10,
                    "type": "LoadImage",
                    "inputs": [],
                    "outputs": [
                        {"name": "IMAGE", "type": "IMAGE", "links": [1]},
                    ],
                    "widgets_values": ["cat.png", "image"],
                },
                {
                    "id": 20,
                    "type": "LoadImage",
                    "inputs": [],
                    "outputs": [
                        {"name": "IMAGE", "type": "IMAGE", "links": [2]},
                    ],
                    "widgets_values": ["dog.png", "image"],
                },
                {
                    "id": 30,
                    "type": "SaveImage",
                    "inputs": [
                        {"name": "images", "type": "IMAGE", "link": 3},
                    ],
                    "outputs": [],
                    "widgets_values": ["output_prefix"],
                },
            ],
            "links": [
                {
                    "id": 1,
                    "origin_id": 10,
                    "origin_slot": 0,
                    "target_id": 30,
                    "target_slot": 0,
                    "type": "IMAGE",
                },
                {
                    "id": 2,
                    "origin_id": 20,
                    "origin_slot": 0,
                    "target_id": 30,
                    "target_slot": 0,
                    "type": "IMAGE",
                },
            ],
        }

        # Normalize nodes to dict (simulating load_source_workflow output)
        normalized = {**source, "nodes": {str(n["id"]): n for n in source["nodes"]}}

        results = collect_type_instances(normalized, "LoadImage")
        assert len(results) == 2

        # Both results present
        nids = {r["node_id"] for r in results}
        assert nids == {"10", "20"}

        # Distinct widget values
        for r in results:
            assert r["class_type"] == "LoadImage"
            wv = {w["name"]: w["value"] for w in r["widget_values"]}
            if r["node_id"] == "10":
                assert wv.get("image") == "cat.png" or wv.get("widget_0") == "cat.png"
            else:
                assert wv.get("image") == "dog.png" or wv.get("widget_0") == "dog.png"

    def test_none_source_returns_empty_list(self) -> None:
        result = collect_type_instances(None, "LoadImage")
        assert result == []

    def test_no_matching_type_returns_empty_list(self) -> None:
        source = {
            "nodes": {
                "1": {"id": 1, "type": "LoadImage", "widgets_values": []},
            }
        }
        result = collect_type_instances(source, "NonExistent")
        assert result == []
