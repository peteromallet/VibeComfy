from __future__ import annotations

from vibecomfy.porting.reorganise import compile_layout_plan
from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts
from vibecomfy.porting.reorganise.parse import parse_layout_plan


def _node(node_id: int, class_type: str, uid: str) -> dict:
    return {
        "id": node_id,
        "type": class_type,
        "class_type": class_type,
        "pos": [0, 0],
        "size": [240, 90],
        "properties": {"vibecomfy_uid": uid},
    }


def _with_io(node: dict, *, inputs: list[dict] | None = None, outputs: list[dict] | None = None) -> dict:
    if inputs is not None:
        node["inputs"] = inputs
    if outputs is not None:
        node["outputs"] = outputs
    return node


def _section_topologies(result) -> dict[str, object]:
    return {topology.section_id: topology for topology in result.section_topologies}


def _sampler_pair_relations(result) -> dict[tuple[str, ...], object]:
    return {
        tuple(ref.uid for ref in relation.samplers): relation
        for relation in result.sampler_relations
        if len(relation.samplers) == 2
    }


def _node_sections(result) -> dict[str, str]:
    return {layout.ref.uid: layout.section_id for layout in result.node_layouts}


def _layouts_by_uid(result) -> dict[str, object]:
    return {layout.ref.uid: layout for layout in result.node_layouts}


def test_compile_layout_plan_orders_sequential_samplers_through_helper_passthrough_edges() -> None:
    ui = {
        "nodes": [
            _with_io(
                _node(1, "KSampler", "base"),
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [10]}],
            ),
            _with_io(
                _node(2, "Reroute", "latent-reroute"),
                inputs=[{"name": "", "type": "*", "link": 10}],
                outputs=[{"name": "", "type": "*", "links": [11]}],
            ),
            _with_io(
                _node(3, "LatentUpscale", "upscale"),
                inputs=[{"name": "samples", "type": "LATENT", "link": 11}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [12]}],
            ),
            _with_io(
                _node(4, "KSampler", "refine"),
                inputs=[{"name": "latent_image", "type": "LATENT", "link": 12}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [13]}],
            ),
            _with_io(
                _node(5, "SaveImage", "save"),
                inputs=[{"name": "images", "type": "LATENT", "link": 13}],
            ),
        ],
        "links": [
            [10, 1, 0, 2, 0, "LATENT"],
            [11, 2, 0, 3, 0, "LATENT"],
            [12, 3, 0, 4, 0, "LATENT"],
            [13, 4, 0, 5, 0, "LATENT"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "base_sampling", "kind": "sampling", "nodes": [["", "base"]]},
                {"id": "latent_bridge", "kind": "latent", "nodes": [["", "upscale"]]},
                {"id": "refine_sampling", "kind": "sampling", "nodes": [["", "refine"]]},
                {"id": "output", "kind": "output", "nodes": [["", "save"]]},
            ],
            "helper_placements": [
                {
                    "helper": ["", "latent-reroute"],
                    "kind": "edge-path",
                    "from": ["", "base"],
                    "to": ["", "upscale"],
                }
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    topologies = _section_topologies(result)
    assert topologies["base_sampling"].rank < topologies["latent_bridge"].rank
    assert topologies["latent_bridge"].rank < topologies["refine_sampling"].rank
    assert topologies["base_sampling"].successor_ids == ("latent_bridge",)
    relations = _sampler_pair_relations(result)
    relation = relations[("base", "refine")]
    assert relation.kind == "sequential"
    assert relation.source.uid == "base"
    assert relation.target.uid == "refine"
    assert [ref.uid for ref in relation.bridge_path] == ["base", "upscale", "refine"]


def test_compile_layout_plan_places_ipadapter_reference_chain_before_sampling() -> None:
    ui = {
        "nodes": [
            _with_io(
                _node(1, "CheckpointLoaderSimple", "checkpoint"),
                outputs=[{"name": "MODEL", "type": "MODEL", "links": [10]}],
            ),
            _with_io(
                _node(2, "LoadImage", "reference-image"),
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            ),
            _with_io(
                _node(3, "CLIPVisionLoader", "clip-vision"),
                outputs=[{"name": "CLIP_VISION", "type": "CLIP_VISION", "links": [12]}],
            ),
            _with_io(
                _node(4, "IPAdapterModelLoader", "ipadapter-model"),
                outputs=[{"name": "IPADAPTER", "type": "IPADAPTER", "links": [13]}],
            ),
            _with_io(
                _node(5, "IPAdapterAdvanced", "apply-ipadapter"),
                inputs=[
                    {"name": "model", "type": "MODEL", "link": 10},
                    {"name": "image", "type": "IMAGE", "link": 11},
                    {"name": "clip_vision", "type": "CLIP_VISION", "link": 12},
                    {"name": "ipadapter", "type": "IPADAPTER", "link": 13},
                ],
                outputs=[{"name": "MODEL", "type": "MODEL", "links": [14]}],
            ),
            _with_io(
                _node(6, "KSampler", "sample"),
                inputs=[{"name": "model", "type": "MODEL", "link": 14}],
            ),
        ],
        "links": [
            [10, 1, 0, 5, 0, "MODEL"],
            [11, 2, 0, 5, 1, "IMAGE"],
            [12, 3, 0, 5, 2, "CLIP_VISION"],
            [13, 4, 0, 5, 3, "IPADAPTER"],
            [14, 5, 0, 6, 0, "MODEL"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "model", "kind": "loaders", "nodes": [["", "checkpoint"]]},
                {
                    "id": "reference_loaders",
                    "kind": "branch",
                    "nodes": [
                        ["", "reference-image"],
                        ["", "clip-vision"],
                        ["", "ipadapter-model"],
                    ],
                },
                {"id": "reference", "kind": "branch", "nodes": [["", "apply-ipadapter"]]},
                {"id": "sampling", "kind": "sampling", "nodes": [["", "sample"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    assert _node_sections(result) == {
        "apply-ipadapter": "reference",
        "checkpoint": "model",
        "clip-vision": "reference_loaders",
        "ipadapter-model": "reference_loaders",
        "reference-image": "reference_loaders",
        "sample": "sampling",
    }
    topologies = _section_topologies(result)
    assert topologies["model"].rank < topologies["reference"].rank < topologies["sampling"].rank
    assert topologies["reference_loaders"].rank < topologies["reference"].rank
    layouts = _layouts_by_uid(result)
    assert layouts["checkpoint"].x < layouts["apply-ipadapter"].x < layouts["sample"].x
    assert layouts["reference-image"].x == layouts["clip-vision"].x == layouts["ipadapter-model"].x
    assert layouts["clip-vision"].y < layouts["ipadapter-model"].y < layouts["reference-image"].y


def test_compile_layout_plan_keeps_parallel_sampler_branches_at_the_same_topology_rank() -> None:
    ui = {
        "nodes": [
            _with_io(_node(1, "LoadImage", "load"), outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [10, 11]}]),
            _with_io(
                _node(2, "KSampler", "sample-a"),
                inputs=[{"name": "image", "type": "IMAGE", "link": 10}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [12]}],
            ),
            _with_io(
                _node(3, "KSampler", "sample-b"),
                inputs=[{"name": "image", "type": "IMAGE", "link": 11}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [13]}],
            ),
            _with_io(_node(4, "SaveImage", "save-a"), inputs=[{"name": "images", "type": "IMAGE", "link": 12}]),
            _with_io(_node(5, "PreviewImage", "save-b"), inputs=[{"name": "images", "type": "IMAGE", "link": 13}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 1, 0, 3, 0, "IMAGE"],
            [12, 2, 0, 4, 0, "IMAGE"],
            [13, 3, 0, 5, 0, "IMAGE"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "input", "kind": "loaders", "nodes": [["", "load"]]},
                {"id": "branch_a", "kind": "branch", "nodes": [["", "sample-a"]]},
                {"id": "branch_b", "kind": "branch", "nodes": [["", "sample-b"]]},
                {"id": "output_a", "kind": "output", "nodes": [["", "save-a"]]},
                {"id": "output_b", "kind": "output", "nodes": [["", "save-b"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    assert _node_sections(result)["sample-a"] == "branch_a"
    assert _node_sections(result)["sample-b"] == "branch_b"
    topologies = _section_topologies(result)
    assert topologies["input"].rank < topologies["branch_a"].rank
    assert topologies["branch_a"].rank == topologies["branch_b"].rank
    relation = _sampler_pair_relations(result)[("sample-a", "sample-b")]
    assert relation.kind == "parallel"
    assert relation.auto_name == compile_layout_plan(plan, extract_graph_facts(ui)).sampler_relations[0].auto_name


def test_compile_layout_plan_reports_mixed_sampler_graphs_when_parallel_and_sequential_pairs_coexist() -> None:
    ui = {
        "nodes": [
            _with_io(_node(1, "LoadImage", "load"), outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [10, 11]}]),
            _with_io(
                _node(2, "KSampler", "sample-a"),
                inputs=[{"name": "image", "type": "IMAGE", "link": 10}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [12]}],
            ),
            _with_io(
                _node(3, "KSampler", "sample-b"),
                inputs=[{"name": "image", "type": "IMAGE", "link": 11}],
            ),
            _with_io(
                _node(4, "LatentUpscale", "upscale"),
                inputs=[{"name": "samples", "type": "LATENT", "link": 12}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [13]}],
            ),
            _with_io(
                _node(5, "KSampler", "sample-c"),
                inputs=[{"name": "latent_image", "type": "LATENT", "link": 13}],
            ),
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 1, 0, 3, 0, "IMAGE"],
            [12, 2, 0, 4, 0, "LATENT"],
            [13, 4, 0, 5, 0, "LATENT"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "input", "kind": "loaders", "nodes": [["", "load"]]},
                {"id": "branch_a", "kind": "branch", "nodes": [["", "sample-a"], ["", "upscale"]]},
                {"id": "branch_b", "kind": "branch", "nodes": [["", "sample-b"]]},
                {"id": "refine", "kind": "sampling", "nodes": [["", "sample-c"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    pair_relations = _sampler_pair_relations(result)
    assert pair_relations[("sample-a", "sample-c")].kind == "sequential"
    assert pair_relations[("sample-a", "sample-b")].kind == "parallel"
    mixed = [relation for relation in result.sampler_relations if len(relation.samplers) == 3]
    assert len(mixed) == 1
    assert mixed[0].kind == "mixed"
    assert [ref.uid for ref in mixed[0].samplers] == ["sample-a", "sample-b", "sample-c"]


def test_compile_layout_plan_collapses_section_cycles_and_ranks_disconnected_islands() -> None:
    ui = {
        "nodes": [
            _with_io(
                _node(1, "KSampler", "cycle-a"),
                inputs=[{"name": "feedback", "type": "LATENT", "link": 11}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [10]}],
            ),
            _with_io(
                _node(2, "KSampler", "cycle-b"),
                inputs=[{"name": "latent", "type": "LATENT", "link": 10}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [11]}],
            ),
            _node(3, "KSampler", "island"),
        ],
        "links": [
            [10, 1, 0, 2, 0, "LATENT"],
            [11, 2, 0, 1, 0, "LATENT"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "cycle_a", "kind": "sampling", "nodes": [["", "cycle-a"]]},
                {"id": "cycle_b", "kind": "sampling", "nodes": [["", "cycle-b"]]},
                {"id": "island", "kind": "sampling", "nodes": [["", "island"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    topologies = _section_topologies(result)
    assert topologies["cycle_a"].scc_id == topologies["cycle_b"].scc_id
    assert topologies["cycle_a"].rank == topologies["cycle_b"].rank
    assert topologies["cycle_a"].island_index != topologies["island"].island_index
    assert result.to_json() == compile_layout_plan(plan, extract_graph_facts(ui)).to_json()
