"""B04 — precedent projection (bounded surface+topology, never raw JSON).

Covers ``project_precedent_topology``: ranking (exact query/class matches →
1-hop → 2-hop), stable ``(class_type, uid)`` ties, induced edges only, the
128-node / 256-edge / 64 KiB bounds, and the always-present
``omitted_node_count`` / ``omitted_edge_count`` /
``global_topology_complete=false`` counters.  Also covers the Hivemind record
view serving surface + topology (never raw workflow JSON) and the
workflow-valued ready-template sanitization.
"""

from __future__ import annotations

from typing import Any

from vibecomfy.executor.precedents import (
    PRECEDENT_MAX_RENDERED_BYTES,
    project_precedent_topology,
    render_precedent_topology,
    sanitize_workflow_text,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _workflow() -> VibeWorkflow:
    wf = VibeWorkflow("prec", WorkflowSource("law"))
    # seed: two KSampler nodes; then 1-hop and 2-hop neighbours.
    wf.nodes["1"] = VibeNode("1", "KSampler", uid="k1")
    wf.nodes["2"] = VibeNode("2", "KSampler", uid="k2")
    wf.nodes["3"] = VibeNode("3", "VAEDecode", uid="v1")
    wf.nodes["4"] = VibeNode("4", "SaveImage", uid="s1")
    wf.nodes["5"] = VibeNode("5", "LoadImage", uid="l1")
    # k1 -> v1 (1-hop from k1), v1 -> s1 (2-hop), l1 -> k2 (1-hop from k2)
    wf.edges.append(VibeEdge("1", "LATENT", "3", "samples"))
    wf.edges.append(VibeEdge("3", "IMAGE", "4", "images"))
    wf.edges.append(VibeEdge("5", "IMAGE", "2", "image"))
    return wf


def _node_refs(topology: dict[str, Any]) -> list[str]:
    return [item.split(" ")[0] for item in topology["nodes"]]


def test_projection_ranks_seed_then_one_hop_then_two_hop() -> None:
    topology = project_precedent_topology(_workflow(), query="KSampler")
    refs = _node_refs(topology)
    assert refs[0] in {"k1", "k2"}
    assert refs[1] in {"k1", "k2"}
    # 1-hop neighbours come before the 2-hop neighbour.
    assert refs.index("v1") < refs.index("s1")
    assert refs.index("l1") < refs.index("s1")


def test_projection_uses_stable_class_uid_ties() -> None:
    a = project_precedent_topology(_workflow(), query="KSampler")
    b = project_precedent_topology(_workflow(), query="KSampler")
    assert a == b
    # The two seed nodes are ordered by (class_type, uid).
    refs = _node_refs(a)
    assert refs[0] == "k1" and refs[1] == "k2"


def test_projection_induced_edges_only() -> None:
    wf = VibeWorkflow("p2", WorkflowSource("law"))
    wf.nodes["1"] = VibeNode("1", "A", uid="a")
    wf.nodes["2"] = VibeNode("2", "B", uid="b")
    wf.nodes["3"] = VibeNode("3", "C", uid="c")
    wf.edges.append(VibeEdge("1", "OUT", "2", "in"))
    wf.edges.append(VibeEdge("2", "OUT", "3", "in"))
    topology = project_precedent_topology(wf, query="A", max_nodes=2)
    # Only the edge whose BOTH endpoints are selected is induced.
    selected = set(_node_refs(topology))
    assert selected == {"a", "b"}
    assert len(topology["edges"]) == 1
    assert topology["edges"][0].startswith("a.OUT")


def test_projection_reports_omitted_counts_and_incomplete() -> None:
    wf = VibeWorkflow("p3", WorkflowSource("law"))
    for i in range(5):
        wf.nodes[str(i + 1)] = VibeNode(str(i + 1), f"C{i}", uid=f"n{i}")
    topology = project_precedent_topology(wf, max_nodes=3)
    assert len(topology["nodes"]) == 3
    assert topology["omitted_node_count"] == 2
    assert topology["omitted_edge_count"] == 0
    assert topology["global_topology_complete"] is False


def test_render_precedent_topology_is_bounded_and_echoes_counters() -> None:
    topology = project_precedent_topology(_workflow(), query="KSampler")
    text = render_precedent_topology(topology)
    assert "## Precedent Topology" in text
    assert "omitted nodes:" in text
    assert "complete: false" in text
    assert len(text.encode("utf-8")) <= PRECEDENT_MAX_RENDERED_BYTES


def test_render_precedent_topology_trims_to_byte_ceiling() -> None:
    topology = {
        "nodes": [f"node{i} (VeryLongClassName{i})" for i in range(20000)],
        "edges": [],
        "omitted_node_count": 0,
        "omitted_edge_count": 0,
        "global_topology_complete": False,
    }
    text = render_precedent_topology(topology, max_bytes=2048)
    assert len(text.encode("utf-8")) <= 2048


# ── Hivemind record view: surface + topology, never raw JSON ─────────────────


def test_serve_hivemind_record_workflow_exposes_surface_and_topology() -> None:
    from vibecomfy.executor.hivemind_tools import serve_hivemind_record

    row = {
        "id": "wf-1",
        "kind": "workflow",
        "payload": {
            "workflow_json": {
                "last_node_id": 2,
                "nodes": [
                    {"id": 1, "type": "KSampler", "pos": [0, 0], "widgets_values": [1, 20, 7.0]},
                    {"id": 2, "type": "VAEDecode", "pos": [100, 0], "widgets_values": [],
                     "inputs": [{"name": "samples", "type": "LATENT", "link": 1}]},
                ],
                "links": [[1, 1, 0, 2, 0, "LATENT"]],
            }
        },
    }
    view = serve_hivemind_record(row, evidence_id="hivemind:external_resources:wf-1")
    assert view.record_type == "workflow"
    assert view.surface_lens is not None
    assert "ksampler = KSampler(" in view.surface_lens
    assert view.topology is not None
    assert view.topology["global_topology_complete"] is False
    assert "omitted_node_count" in view.topology
    assert "omitted_edge_count" in view.topology
    # The raw workflow JSON never rides in the view.
    assert "nodes" not in view.surface_lens
    assert '"links"' not in view.surface_lens


def test_sanitize_workflow_text_returns_none_for_python() -> None:
    assert sanitize_workflow_text("x = 1\n") is None
    assert sanitize_workflow_text("not json at all") is None


def test_sanitize_workflow_text_projects_workflow_json() -> None:
    import json

    payload = {
        "last_node_id": 1,
        "nodes": [{"id": 1, "type": "KSampler", "pos": [0, 0], "widgets_values": [1, 20, 7.0]}],
        "links": [],
    }
    view = sanitize_workflow_text(json.dumps(payload))
    assert view is not None
    assert view["shape"] == "ui"
    assert view["surface_lens"] is not None
    assert view["topology"]["global_topology_complete"] is False


def test_ready_template_load_sanitizes_workflow_valued_content(tmp_path: Any) -> None:
    import json
    from pathlib import Path

    from vibecomfy.executor.lookup_tools import ready_template_load

    root = tmp_path / "templates"
    (root / "wf").mkdir(parents=True)
    payload = {
        "last_node_id": 1,
        "nodes": [{"id": 1, "type": "KSampler", "pos": [0, 0], "widgets_values": [1, 20, 7.0]}],
        "links": [],
    }
    (root / "wf.json.py").write_text(json.dumps(payload), encoding="utf-8")

    result = ready_template_load("wf.json", roots=[root], include_content=True)
    body = result.result
    assert body["workflow_view"] is not None
    assert body["workflow_view"]["topology"]["global_topology_complete"] is False
