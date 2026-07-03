from __future__ import annotations

from copy import deepcopy

from vibecomfy.porting.reorganise import LayoutCompileOptions, compile_layout_plan
from vibecomfy.porting.reorganise.compile import (
    COMPILE_ISSUE_BACKWARD_EDGE_RATIO_HIGH,
    COMPILE_ISSUE_CROSSING_PROXY_HIGH,
    COMPILE_ISSUE_GROUP_OVERLAP,
    COMPILE_ISSUE_HELPER_DISTANCE_HIGH,
    COMPILE_ISSUE_IDEMPOTENCE_DELTA,
    COMPILE_ISSUE_MINIMUM_GUTTER,
    COMPILE_ISSUE_NODE_OVERLAP,
    COMPILE_HUGE_WORKFLOW_NODE_THRESHOLD,
    COMPILE_LARGE_SECTION_CLUSTER_SIZE,
    COMPILE_METRIC_BACKWARD_EDGE_RATIO,
    COMPILE_METRIC_CROSSING_PROXY_COUNT,
    COMPILE_METRIC_GROUP_OVERLAP_COUNT,
    COMPILE_METRIC_HELPER_DISTANCE_MAX,
    COMPILE_METRIC_IDEMPOTENCE_DELTA,
    COMPILE_METRIC_MINIMUM_GUTTER,
    COMPILE_METRIC_NODE_OVERLAP_COUNT,
    COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED,
    CompiledGroupLayout,
    CompiledNodeLayout,
    LayoutCandidatePatch,
    _build_report,
    compile_layout_plan_from_ui,
    structural_hash_for_layout_facts,
)
from vibecomfy.porting.layout_store import STORE_VERSION, read_store, write_store
from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts
from vibecomfy.porting.reorganise.parse import parse_layout_plan
from vibecomfy.porting.reorganise.plan_types import (
    CanonicalNodeRef,
    LayoutPlanV1,
    LayoutSection,
    ROLE_HINT_HELPER,
    ROLE_HINT_UNKNOWN,
)


def _node(node_id: int, class_type: str, uid: str) -> dict:
    return {
        "id": node_id,
        "type": class_type,
        "class_type": class_type,
        "pos": [node_id * 10, node_id * 20],
        "size": [200 + node_id, 80 + node_id],
        "properties": {"vibecomfy_uid": uid, "kept": uid},
    }


def _with_io(node: dict, *, inputs: list[dict] | None = None, outputs: list[dict] | None = None) -> dict:
    if inputs is not None:
        node["inputs"] = inputs
    if outputs is not None:
        node["outputs"] = outputs
    return node


def _ui() -> dict:
    return {
        "nodes": [
            _node(5, "SaveImage", "save"),
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(6, "Reroute", "reroute"),
            _node(3, "KSampler", "sample"),
            _node(2, "CLIPTextEncode", "positive"),
            _node(4, "VAEDecode", "decode"),
        ],
        "links": [
            [1, 1, 0, 3, 0, "MODEL"],
            [2, 2, 0, 3, 1, "CONDITIONING"],
            [3, 3, 0, 4, 0, "LATENT"],
            [4, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [{"title": "Existing", "bounding": [0, 0, 100, 100], "nodes": [1]}],
        "extra": {"ds": {"scale": 1.0, "offset": [0, 0]}},
        "state": {"lastRerouteId": 12},
    }


def _node_sections(result) -> dict[str, str]:
    return {layout.ref.uid: layout.section_id for layout in result.node_layouts}


def _layouts_by_uid(result) -> dict[str, object]:
    return {layout.ref.uid: layout for layout in result.node_layouts}


def _groups_by_id(result) -> dict[str, object]:
    return {group.id: group for group in result.group_layouts}


def _group_templates_by_id(result) -> dict[str, str]:
    return {group.id: group.template for group in result.group_layouts}


def _group_titles_by_id(result) -> dict[str, str]:
    return {group.id: group.title for group in result.group_layouts}


def _valid_plan() -> LayoutPlanV1:
    return parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "sampling", "kind": "sampling", "nodes": [["", "sample"]]},
                {"id": "loaders", "kind": "loaders", "nodes": [["", "checkpoint"]]},
                {"id": "conditioning", "kind": "conditioning", "nodes": [["", "positive"]]},
                {
                    "id": "output",
                    "kind": "output",
                    "nodes": [["", "decode"], ["", "save"]],
                },
            ],
            "helper_placements": [
                {
                    "helper": ["", "reroute"],
                    "kind": "inside-section",
                    "section_id": "sampling",
                }
            ],
            "unassigned_policy": "reject",
        }
    )


def test_compile_layout_plan_returns_public_contract_and_candidate_patch() -> None:
    facts = extract_graph_facts(_ui())

    result = compile_layout_plan(_valid_plan(), facts)

    assert result.ok is True
    assert result.validation_report.ok is True
    assert result.report.verdict == "ok"
    assert [metric.name for metric in result.metrics] == [
        "compiled_node_layout_count",
        "compiled_group_layout_count",
        "compiled_helper_layout_count",
        COMPILE_METRIC_NODE_OVERLAP_COUNT,
        COMPILE_METRIC_GROUP_OVERLAP_COUNT,
        COMPILE_METRIC_BACKWARD_EDGE_RATIO,
        COMPILE_METRIC_CROSSING_PROXY_COUNT,
        COMPILE_METRIC_MINIMUM_GUTTER,
        COMPILE_METRIC_HELPER_DISTANCE_MAX,
        COMPILE_METRIC_IDEMPOTENCE_DELTA,
        "structural_hash_unchanged",
    ]
    assert next(
        metric.value
        for metric in result.metrics
        if metric.name == COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED
    ) is True
    assert [layout.ref.to_json() for layout in result.node_layouts] == [
        ["", "checkpoint"],
        ["", "decode"],
        ["", "positive"],
        ["", "reroute"],
        ["", "sample"],
        ["", "save"],
    ]
    patch = result.candidate_patch.to_json()
    assert list(patch) == [
        "store_version",
        "vibecomfy_version",
        "schema_hash",
        "entries",
        "groups",
        "extra",
        "lastRerouteId",
        "definitions",
        "virtual_wires",
        "unkeyed",
    ]
    assert list(patch["entries"]) == [
        "checkpoint",
        "decode",
        "positive",
        "reroute",
        "sample",
        "save",
    ]
    assert [group["title"] for group in patch["groups"]] == [
        "Conditioning",
        "Loaders",
        "Output",
        "Sampling",
    ]
    assert patch["entries"]["checkpoint"]["properties"]["kept"] == "checkpoint"
    assert patch["extra"] == {"ds": {"scale": 1.0, "offset": [0, 0]}}
    assert patch["lastRerouteId"] == 12


def test_compile_layout_plan_candidate_patch_round_trips_as_layout_store_envelope(tmp_path) -> None:
    sidecar = {
        "store_version": 1,
        "vibecomfy_version": "sidecar-version",
        "schema_hash": "stale-schema",
        "entries": {
            "checkpoint": {
                "pos": [999, 999],
                "size": [123, 45],
                "flags": {"collapsed": True},
                "color": "#111111",
                "bgcolor": "#222222",
                "mode": 4,
                "properties": {"vibecomfy_uid": "checkpoint", "sidecar": True},
            }
        },
        "groups": [{"title": "Old Group", "bounding": [1, 2, 3, 4], "nodes": ["checkpoint"]}],
        "extra": {"ds": {"scale": 0.75, "offset": [9, 10]}, "view": "kept"},
        "lastRerouteId": 44,
        "definitions": {"subgraphs": [{"name": "Preserved", "nodes": []}]},
        "virtual_wires": {
            "wire-1": {
                "type": "GetNode",
                "channel": "MODEL",
                "endpoints": ["checkpoint", "sample"],
            }
        },
        "unkeyed": ["999"],
    }
    facts = extract_graph_facts(_ui(), sidecar_envelope=sidecar)

    result = compile_layout_plan(_valid_plan(), facts)
    patch = result.candidate_patch.to_json()

    assert patch["store_version"] == STORE_VERSION
    assert patch["vibecomfy_version"] == "sidecar-version"
    assert patch["schema_hash"] != "stale-schema"
    assert patch["extra"] == sidecar["extra"]
    assert patch["lastRerouteId"] == 44
    assert patch["definitions"] == sidecar["definitions"]
    assert patch["virtual_wires"] == sidecar["virtual_wires"]
    assert patch["unkeyed"] == ["999"]
    assert patch["entries"]["checkpoint"]["pos"] != [999, 999]
    assert patch["entries"]["checkpoint"]["properties"]["kept"] == "checkpoint"
    assert [group["title"] for group in patch["groups"]] != ["Old Group"]

    py_path = tmp_path / "candidate.py"
    write_store(py_path, patch)
    assert read_store(py_path) == patch


def test_compile_layout_plan_preserves_virtual_wires_from_facts_when_sidecar_section_absent() -> None:
    ui = deepcopy(_ui())
    ui["extra"]["virtual_wires"] = {
        "ui-wire": {
            "type": "SetNode",
            "channel": "LATENT",
            "endpoints": ["positive", "sample"],
        }
    }
    facts = extract_graph_facts(
        ui,
        sidecar_envelope={
            "entries": {},
            "groups": [],
            "extra": {"ds": {"scale": 1, "offset": [0, 0]}},
            "lastRerouteId": 12,
            "definitions": {},
        },
    )

    patch = compile_layout_plan(_valid_plan(), facts).candidate_patch.to_json()

    assert patch["virtual_wires"] == ui["extra"]["virtual_wires"]


def test_structural_hash_excludes_ui_only_furniture_and_changes_for_runtime_structure() -> None:
    ui = _ui()
    furniture_only = deepcopy(ui)
    furniture_only["nodes"][0]["pos"] = [999, 888]
    furniture_only["nodes"][0]["size"] = [333, 222]
    furniture_only["nodes"][0]["flags"] = {"collapsed": True}
    furniture_only["groups"] = [{"title": "Different", "bounding": [10, 20, 30, 40], "nodes": [5]}]
    furniture_only["extra"] = {"ds": {"scale": 2.0, "offset": [100, 200]}}
    furniture_only["state"] = {"lastRerouteId": 999}

    structural = deepcopy(ui)
    structural["nodes"][0]["type"] = "PreviewImage"
    structural["nodes"][0]["class_type"] = "PreviewImage"

    base_hash = structural_hash_for_layout_facts(extract_graph_facts(ui))

    assert structural_hash_for_layout_facts(extract_graph_facts(furniture_only)) == base_hash
    assert structural_hash_for_layout_facts(extract_graph_facts(structural)) != base_hash


def test_compile_layout_plan_candidate_patch_is_near_idempotent_with_sidecar_input() -> None:
    first = compile_layout_plan(_valid_plan(), extract_graph_facts(_ui()))
    second = compile_layout_plan(
        _valid_plan(),
        extract_graph_facts(_ui(), sidecar_envelope=first.candidate_patch.to_json()),
    )

    assert first.structural_hash_before == second.structural_hash_before
    assert first.structural_hash_after == second.structural_hash_after
    assert first.candidate_patch.to_json() == second.candidate_patch.to_json()


def test_compile_layout_plan_reports_validation_failures_without_patch() -> None:
    facts = extract_graph_facts(_ui())
    invalid_plan = LayoutPlanV1(
        sections=(
            LayoutSection(
                id="sampling",
                kind="sampling",
                nodes=(CanonicalNodeRef("", "sample"), CanonicalNodeRef("", "save")),
            ),
            LayoutSection(
                id="output",
                kind="output",
                nodes=(
                    CanonicalNodeRef("", "checkpoint"),
                    CanonicalNodeRef("", "positive"),
                    CanonicalNodeRef("", "decode"),
                    CanonicalNodeRef("", "save"),
                ),
            ),
        ),
        unassigned_policy="reject",
    )

    result = compile_layout_plan(invalid_plan, facts)

    assert result.ok is False
    assert result.report.verdict == "blocked"
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["duplicate_primary_ownership"]
    assert result.node_layouts == ()
    assert result.group_layouts == ()
    assert result.candidate_patch.to_json()["entries"] == {}


def test_compile_layout_plan_json_order_is_deterministic() -> None:
    facts = extract_graph_facts(_ui())
    options = LayoutCompileOptions(spacing_preset="compact")

    first = compile_layout_plan(_valid_plan(), facts, options=options).to_json()
    second = compile_layout_plan(_valid_plan(), facts, options=options).to_json()

    assert first == second
    assert list(first["candidate_patch"]["entries"]) == sorted(first["candidate_patch"]["entries"])
    assert [group["title"] for group in first["candidate_patch"]["groups"]] == sorted(
        group["title"] for group in first["candidate_patch"]["groups"]
    )


def test_compile_layout_plan_does_not_mutate_plan_or_facts_or_ui() -> None:
    ui = _ui()
    facts = extract_graph_facts(ui)
    plan = _valid_plan()
    ui_before = deepcopy(ui)
    facts_before = facts.to_json()
    plan_before = plan.to_json()

    compile_layout_plan(plan, facts)
    compile_layout_plan_from_ui(plan, ui)

    assert plan.to_json() == plan_before
    assert facts.to_json() == facts_before
    assert ui == ui_before


def test_compile_layout_plan_classifies_simple_t2i_unassigned_nodes_into_sections() -> None:
    facts = extract_graph_facts(_ui())
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": []},
                {"id": "conditioning", "kind": "conditioning", "nodes": []},
                {"id": "sampling", "kind": "sampling", "nodes": []},
                {"id": "decode", "kind": "decode", "nodes": []},
                {"id": "output", "kind": "output", "nodes": []},
            ],
            "unassigned_policy": "classify_deterministically",
        }
    )

    result = compile_layout_plan(plan, facts)

    assert result.ok is True
    assert _node_sections(result) == {
        "checkpoint": "loaders",
        "decode": "output",
        "positive": "conditioning",
        "reroute": "__helpers__",
        "sample": "sampling",
        "save": "output",
    }
    assert [diagnostic.code for diagnostic in result.validation_report.diagnostics] == [
        "unassigned_classified_deterministically",
        "unassigned_classified_deterministically",
        "unassigned_classified_deterministically",
        "unassigned_classified_deterministically",
        "unassigned_classified_deterministically",
    ]


def test_compile_layout_plan_classifies_prompt_pairs_to_conditioning() -> None:
    ui = {
        "nodes": [
            _node(1, "CLIPLoader", "clip"),
            _node(2, "CLIPTextEncode", "positive"),
            _node(3, "CLIPTextEncode", "negative"),
            _node(4, "KSampler", "sample"),
        ],
        "links": [
            [10, 1, 0, 2, 0, "CLIP"],
            [11, 1, 0, 3, 0, "CLIP"],
            [12, 2, 0, 4, 1, "CONDITIONING"],
            [13, 3, 0, 4, 2, "CONDITIONING"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": []},
                {"id": "conditioning", "kind": "conditioning", "nodes": []},
                {"id": "sampling", "kind": "sampling", "nodes": []},
            ],
            "unassigned_policy": "classify_deterministically",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    assert _node_sections(result) == {
        "clip": "loaders",
        "negative": "conditioning",
        "positive": "conditioning",
        "sample": "sampling",
    }


def test_compile_layout_plan_uses_shared_home_as_canonical_owner() -> None:
    facts = extract_graph_facts(_ui())
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": []},
                {"id": "conditioning", "kind": "conditioning", "nodes": [["", "positive"]]},
                {"id": "sampling", "kind": "sampling", "nodes": [["", "sample"]]},
                {"id": "output", "kind": "output", "nodes": [["", "decode"], ["", "save"]]},
            ],
            "shared_nodes": [{"node": ["", "checkpoint"], "home": "loaders"}],
            "helper_placements": [
                {
                    "helper": ["", "reroute"],
                    "kind": "inside-section",
                    "section_id": "sampling",
                }
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, facts)

    assert result.ok is True
    assert _node_sections(result)["checkpoint"] == "loaders"
    assert _node_sections(result)["reroute"] == "sampling"
    assert [ref.uid for ref in next(group for group in result.group_layouts if group.id == "loaders").node_refs] == [
        "checkpoint"
    ]


def test_compile_layout_plan_handles_helper_only_graphs_without_primary_owners() -> None:
    ui = {
        "nodes": [
            _node(1, "Reroute", "reroute"),
            _node(2, "MarkdownNote", "note"),
        ],
        "links": [],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [{"id": "utility", "kind": "utility", "nodes": []}],
            "helper_placements": [
                {
                    "helper": ["", "reroute"],
                    "kind": "inside-section",
                    "section_id": "utility",
                },
                {
                    "helper": ["", "note"],
                    "kind": "inside-section",
                    "section_id": "utility",
                },
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    assert _node_sections(result) == {"note": "utility", "reroute": "utility"}
    assert result.metrics[2].value == 2
    assert [group.title for group in result.group_layouts] == ["Utility"]


def test_compile_layout_plan_rejects_missing_primary_ownership_without_patch() -> None:
    facts = extract_graph_facts(_ui())
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [{"id": "sampling", "kind": "sampling", "nodes": [["", "sample"]]}],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, facts)

    assert result.ok is False
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "missing_primary_ownership",
        "missing_primary_ownership",
        "missing_primary_ownership",
        "missing_primary_ownership",
    ]
    assert result.candidate_patch.to_json()["entries"] == {}


def test_compile_layout_plan_preserves_coherent_existing_group_ownership_for_unassigned_nodes() -> None:
    ui = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "CLIPTextEncode", "positive"),
            _node(3, "CLIPTextEncode", "negative"),
            _node(4, "KSampler", "sample"),
            _node(5, "SaveImage", "save"),
        ],
        "links": [
            [10, 1, 0, 2, 0, "CLIP"],
            [11, 1, 0, 3, 0, "CLIP"],
            [12, 2, 0, 4, 1, "CONDITIONING"],
            [13, 3, 0, 4, 2, "CONDITIONING"],
            [14, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [{"title": "Prompts", "bounding": [10, 30, 260, 140], "nodes": [2, 3]}],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": []},
                {"id": "sampling", "kind": "sampling", "nodes": [["", "sample"]]},
                {"id": "output", "kind": "output", "nodes": [["", "save"]]},
            ],
            "unassigned_policy": "preserve_existing",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    sections = _node_sections(result)
    assert sections["checkpoint"] == "loaders"
    assert sections["positive"] == "__existing_root_0__"
    assert sections["negative"] == "__existing_root_0__"
    assert _group_titles_by_id(result)["__existing_root_0__"] == "Prompts"


def test_compile_layout_plan_places_sections_by_semantic_minimum_rank_and_band() -> None:
    result = compile_layout_plan(_valid_plan(), extract_graph_facts(_ui()))

    layouts = _layouts_by_uid(result)
    assert layouts["checkpoint"].x < layouts["positive"].x < layouts["sample"].x < layouts["decode"].x
    assert layouts["checkpoint"].y < layouts["sample"].y
    assert layouts["decode"].x == layouts["save"].x

    groups = _groups_by_id(result)
    assert groups["loaders"].color == "#3f6f8f"
    assert groups["conditioning"].color == "#7b5ea7"
    assert groups["sampling"].color == "#9a6a3a"
    assert groups["output"].color == "#8a5f68"
    assert "spacing_preset" not in _valid_plan().to_json()


def test_compile_layout_plan_spacing_presets_scale_ranked_positions_deterministically() -> None:
    facts = extract_graph_facts(_ui())

    compact = _layouts_by_uid(
        compile_layout_plan(_valid_plan(), facts, options=LayoutCompileOptions(spacing_preset="compact"))
    )
    balanced = _layouts_by_uid(compile_layout_plan(_valid_plan(), facts))
    wide = _layouts_by_uid(
        compile_layout_plan(_valid_plan(), facts, options=LayoutCompileOptions(spacing_preset="wide"))
    )

    assert compact["sample"].x < balanced["sample"].x < wide["sample"].x
    assert compact["sample"].y < balanced["sample"].y < wide["sample"].y
    assert compile_layout_plan(_valid_plan(), facts).to_json() == compile_layout_plan(
        _valid_plan(), facts
    ).to_json()


def test_compile_layout_plan_stacks_same_rank_parallel_sections_in_rows() -> None:
    ui = {
        "nodes": [
            _with_io(_node(1, "CheckpointLoaderSimple", "checkpoint"), outputs=[{"name": "MODEL", "type": "MODEL", "links": [10, 11]}]),
            _with_io(
                _node(2, "KSampler", "sample-a"),
                inputs=[{"name": "model", "type": "MODEL", "link": 10}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [12]}],
            ),
            _with_io(
                _node(3, "KSampler", "sample-b"),
                inputs=[{"name": "model", "type": "MODEL", "link": 11}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [13]}],
            ),
            _with_io(_node(4, "VAEDecode", "decode"), inputs=[{"name": "samples", "type": "LATENT", "link": 12}]),
            _with_io(_node(5, "PreviewImage", "preview"), inputs=[{"name": "images", "type": "LATENT", "link": 13}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "MODEL"],
            [11, 1, 0, 3, 0, "MODEL"],
            [12, 2, 0, 4, 0, "LATENT"],
            [13, 3, 0, 5, 0, "LATENT"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": [["", "checkpoint"]]},
                {"id": "branch_a", "kind": "branch", "nodes": [["", "sample-a"]]},
                {"id": "branch_b", "kind": "branch", "nodes": [["", "sample-b"]]},
                {"id": "decode", "kind": "decode", "nodes": [["", "decode"]]},
                {"id": "output", "kind": "output", "nodes": [["", "preview"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    layouts = _layouts_by_uid(result)
    assert layouts["sample-a"].x == layouts["sample-b"].x
    assert layouts["sample-a"].y < layouts["sample-b"].y
    assert layouts["checkpoint"].x < layouts["sample-a"].x < layouts["decode"].x < layouts["preview"].x
    groups = _groups_by_id(result)
    assert groups["branch_a"].color == "#6f6a9a"
    assert groups["branch_b"].color == "#6f6a9a"


def test_compile_layout_plan_selects_named_section_templates_deterministically() -> None:
    nodes = [
        _node(1, "PrimitiveNode", "single"),
        _with_io(_node(2, "PrimitiveNode", "pair-a"), outputs=[{"name": "out", "type": "*", "links": [20]}]),
        _with_io(_node(3, "PrimitiveNode", "pair-b"), inputs=[{"name": "in", "type": "*", "link": 20}]),
        _node(4, "CheckpointLoaderSimple", "row-loader"),
        _node(5, "CLIPTextEncode", "row-text"),
        _node(6, "KSampler", "row-sampler"),
        _with_io(_node(7, "PrimitiveNode", "pipe-a"), outputs=[{"name": "out", "type": "*", "links": [21]}]),
        _with_io(
            _node(8, "PrimitiveNode", "pipe-b"),
            inputs=[{"name": "in", "type": "*", "link": 21}],
            outputs=[{"name": "out", "type": "*", "links": [22]}],
        ),
        _with_io(_node(9, "PrimitiveNode", "pipe-c"), inputs=[{"name": "in", "type": "*", "link": 22}]),
        _node(10, "CLIPTextEncode", "alt-a"),
        _node(11, "CLIPTextEncode", "alt-b"),
        _node(12, "PrimitiveNode", "grid-a"),
        _node(13, "PrimitiveNode", "grid-b"),
        _node(14, "PrimitiveNode", "grid-c"),
        _node(15, "PrimitiveNode", "grid-d"),
        _node(16, "PrimitiveNode", "grid-e"),
        _with_io(_node(17, "PrimitiveNode", "note-main"), outputs=[{"name": "out", "type": "*", "links": [23]}]),
        _with_io(_node(18, "PrimitiveNode", "note-next"), inputs=[{"name": "in", "type": "*", "link": 23}]),
        _node(19, "MarkdownNote", "note-text"),
    ]
    ui = {
        "nodes": nodes,
        "links": [
            [20, 2, 0, 3, 0, "*"],
            [21, 7, 0, 8, 0, "*"],
            [22, 8, 0, 9, 0, "*"],
            [23, 17, 0, 18, 0, "*"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "single", "kind": "custom", "nodes": [["", "single"]]},
                {"id": "pair", "kind": "custom", "nodes": [["", "pair-a"], ["", "pair-b"]]},
                {
                    "id": "row",
                    "kind": "custom",
                    "nodes": [["", "row-loader"], ["", "row-text"], ["", "row-sampler"]],
                },
                {
                    "id": "pipeline",
                    "kind": "custom",
                    "nodes": [["", "pipe-a"], ["", "pipe-b"], ["", "pipe-c"]],
                },
                {"id": "alternatives", "kind": "custom", "nodes": [["", "alt-a"], ["", "alt-b"]]},
                {
                    "id": "grid",
                    "kind": "custom",
                    "nodes": [
                        ["", "grid-a"],
                        ["", "grid-b"],
                        ["", "grid-c"],
                        ["", "grid-d"],
                        ["", "grid-e"],
                    ],
                },
                {"id": "notes", "kind": "utility", "nodes": [["", "note-main"], ["", "note-next"]]},
            ],
            "helper_placements": [
                {"helper": ["", "note-text"], "kind": "inside-section", "section_id": "notes"}
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    assert _group_templates_by_id(result) == {
        "alternatives": "alternatives",
        "grid": "grid",
        "notes": "notes_sidebar",
        "pair": "pair",
        "pipeline": "pipeline",
        "row": "row",
        "single": "single",
    }
    layouts = _layouts_by_uid(result)
    assert layouts["pair-a"].x == layouts["pair-b"].x
    assert layouts["pipe-a"].x < layouts["pipe-b"].x < layouts["pipe-c"].x
    assert layouts["row-loader"].y == layouts["row-text"].y == layouts["row-sampler"].y
    assert layouts["note-main"].x < layouts["note-text"].x
    assert compile_layout_plan(plan, extract_graph_facts(ui)).to_json() == result.to_json()


def test_compile_layout_plan_places_fan_in_and_fan_out_templates() -> None:
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "fan-in-a"), outputs=[{"name": "out", "type": "*", "links": [30]}]),
            _with_io(_node(2, "PrimitiveNode", "fan-in-b"), outputs=[{"name": "out", "type": "*", "links": [31]}]),
            _with_io(
                _node(3, "PrimitiveNode", "fan-in-sink"),
                inputs=[{"name": "a", "type": "*", "link": 30}, {"name": "b", "type": "*", "link": 31}],
            ),
            _with_io(_node(4, "PrimitiveNode", "fan-out-source"), outputs=[{"name": "out", "type": "*", "links": [32, 33]}]),
            _with_io(_node(5, "PrimitiveNode", "fan-out-a"), inputs=[{"name": "in", "type": "*", "link": 32}]),
            _with_io(_node(6, "PrimitiveNode", "fan-out-b"), inputs=[{"name": "in", "type": "*", "link": 33}]),
        ],
        "links": [
            [30, 1, 0, 3, 0, "*"],
            [31, 2, 0, 3, 1, "*"],
            [32, 4, 0, 5, 0, "*"],
            [33, 4, 0, 6, 0, "*"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "fan_in",
                    "kind": "custom",
                    "nodes": [["", "fan-in-a"], ["", "fan-in-b"], ["", "fan-in-sink"]],
                },
                {
                    "id": "fan_out",
                    "kind": "custom",
                    "nodes": [["", "fan-out-source"], ["", "fan-out-a"], ["", "fan-out-b"]],
                },
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    assert _group_templates_by_id(result) == {"fan_in": "fan_in", "fan_out": "fan_out"}
    layouts = _layouts_by_uid(result)
    assert layouts["fan-in-a"].x == layouts["fan-in-b"].x < layouts["fan-in-sink"].x
    assert layouts["fan-in-a"].y < layouts["fan-in-b"].y
    assert layouts["fan-out-source"].x < layouts["fan-out-a"].x == layouts["fan-out-b"].x
    assert layouts["fan-out-a"].y < layouts["fan-out-b"].y


def test_compile_layout_plan_places_parallel_branches_and_hub_spokes_templates() -> None:
    ui = {
        "nodes": [
            _with_io(_node(1, "LoadImage", "branch-source"), outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [40, 41]}]),
            _with_io(
                _node(2, "KSampler", "branch-a"),
                inputs=[{"name": "image", "type": "IMAGE", "link": 40}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [42]}],
            ),
            _with_io(
                _node(3, "KSampler", "branch-b"),
                inputs=[{"name": "image", "type": "IMAGE", "link": 41}],
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [43]}],
            ),
            _with_io(
                _node(4, "ImageBlend", "branch-terminal"),
                inputs=[{"name": "a", "type": "IMAGE", "link": 42}, {"name": "b", "type": "IMAGE", "link": 43}],
            ),
            _with_io(_node(5, "PrimitiveNode", "hub-in"), outputs=[{"name": "out", "type": "*", "links": [44]}]),
            _with_io(
                _node(6, "PrimitiveNode", "hub"),
                inputs=[{"name": "in", "type": "*", "link": 44}],
                outputs=[{"name": "out", "type": "*", "links": [45, 46]}],
            ),
            _with_io(_node(7, "PrimitiveNode", "hub-out-a"), inputs=[{"name": "in", "type": "*", "link": 45}]),
            _with_io(_node(8, "PrimitiveNode", "hub-out-b"), inputs=[{"name": "in", "type": "*", "link": 46}]),
        ],
        "links": [
            [40, 1, 0, 2, 0, "IMAGE"],
            [41, 1, 0, 3, 0, "IMAGE"],
            [42, 2, 0, 4, 0, "IMAGE"],
            [43, 3, 0, 4, 1, "IMAGE"],
            [44, 5, 0, 6, 0, "*"],
            [45, 6, 0, 7, 0, "*"],
            [46, 6, 0, 8, 0, "*"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "branches",
                    "kind": "branch",
                    "nodes": [
                        ["", "branch-source"],
                        ["", "branch-a"],
                        ["", "branch-b"],
                        ["", "branch-terminal"],
                    ],
                },
                {
                    "id": "hub",
                    "kind": "custom",
                    "nodes": [["", "hub-in"], ["", "hub"], ["", "hub-out-a"], ["", "hub-out-b"]],
                },
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    assert _group_templates_by_id(result) == {"branches": "parallel_branches", "hub": "hub_and_spokes"}
    layouts = _layouts_by_uid(result)
    assert layouts["branch-source"].x < layouts["branch-a"].x == layouts["branch-b"].x
    assert layouts["branch-a"].x < layouts["branch-terminal"].x
    assert layouts["branch-a"].y < layouts["branch-b"].y
    assert layouts["hub-in"].x < layouts["hub"].x < layouts["hub-out-a"].x
    assert layouts["hub-out-a"].x == layouts["hub-out-b"].x


def test_compile_layout_plan_orders_controlnet_style_parallel_conditioning_branches() -> None:
    ui = {
        "nodes": [
            _with_io(
                _node(1, "CheckpointLoaderSimple", "checkpoint"),
            ),
            _with_io(
                _node(2, "CLIPTextEncode", "prompt"),
                outputs=[{"name": "CONDITIONING", "type": "CONDITIONING", "links": [10]}],
            ),
            _with_io(
                _node(3, "LoadImage", "control-image"),
                outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            ),
            _with_io(
                _node(4, "ControlNetLoader", "controlnet"),
                outputs=[{"name": "CONTROL_NET", "type": "CONTROL_NET", "links": [12]}],
            ),
            _with_io(
                _node(5, "ControlNetApplyAdvanced", "apply-control"),
                inputs=[
                    {"name": "positive", "type": "CONDITIONING", "link": 10},
                    {"name": "image", "type": "IMAGE", "link": 11},
                    {"name": "control_net", "type": "CONTROL_NET", "link": 12},
                ],
                outputs=[{"name": "CONDITIONING", "type": "CONDITIONING", "links": [13]}],
            ),
            _with_io(
                _node(6, "KSampler", "sample"),
                inputs=[
                    {"name": "positive", "type": "CONDITIONING", "link": 13},
                ],
            ),
        ],
        "links": [
            [10, 2, 0, 5, 0, "CONDITIONING"],
            [11, 3, 0, 5, 1, "IMAGE"],
            [12, 4, 0, 5, 2, "CONTROL_NET"],
            [13, 5, 0, 6, 0, "CONDITIONING"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "model", "kind": "loaders", "nodes": [["", "checkpoint"]]},
                {"id": "prompt", "kind": "conditioning", "nodes": [["", "prompt"]]},
                {
                    "id": "control_inputs",
                    "kind": "branch",
                    "nodes": [["", "control-image"], ["", "controlnet"]],
                },
                {
                    "id": "controlnet",
                    "kind": "branch",
                    "nodes": [["", "apply-control"]],
                },
                {"id": "sampling", "kind": "sampling", "nodes": [["", "sample"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    topologies = {topology.section_id: topology for topology in result.section_topologies}
    assert topologies["prompt"].rank == topologies["control_inputs"].rank
    assert topologies["prompt"].rank < topologies["controlnet"].rank < topologies["sampling"].rank
    assert topologies["model"].island_index != topologies["sampling"].island_index
    layouts = _layouts_by_uid(result)
    assert layouts["prompt"].x < layouts["sample"].x
    assert layouts["apply-control"].x < layouts["sample"].x
    assert layouts["control-image"].x == layouts["controlnet"].x
    assert layouts["control-image"].y != layouts["controlnet"].y
    assert _group_templates_by_id(result)["control_inputs"] == "alternatives"


def test_compile_layout_plan_keeps_shared_model_and_vae_single_owned_across_parallel_outputs() -> None:
    ui = {
        "nodes": [
            _with_io(
                _node(1, "CheckpointLoaderSimple", "checkpoint"),
                outputs=[
                    {"name": "MODEL", "type": "MODEL", "links": [10, 11]},
                    {"name": "VAE", "type": "VAE", "links": [14, 15]},
                ],
            ),
            _with_io(
                _node(2, "KSampler", "sample-a"),
                inputs=[{"name": "model", "type": "MODEL", "link": 10}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [12]}],
            ),
            _with_io(
                _node(3, "KSampler", "sample-b"),
                inputs=[{"name": "model", "type": "MODEL", "link": 11}],
                outputs=[{"name": "LATENT", "type": "LATENT", "links": [13]}],
            ),
            _with_io(
                _node(4, "VAEDecode", "decode-a"),
                inputs=[
                    {"name": "samples", "type": "LATENT", "link": 12},
                    {"name": "vae", "type": "VAE", "link": 14},
                ],
            ),
            _with_io(
                _node(5, "VAEDecode", "decode-b"),
                inputs=[
                    {"name": "samples", "type": "LATENT", "link": 13},
                    {"name": "vae", "type": "VAE", "link": 15},
                ],
            ),
        ],
        "links": [
            [10, 1, 0, 2, 0, "MODEL"],
            [11, 1, 0, 3, 0, "MODEL"],
            [12, 2, 0, 4, 0, "LATENT"],
            [13, 3, 0, 5, 0, "LATENT"],
            [14, 1, 1, 4, 1, "VAE"],
            [15, 1, 1, 5, 1, "VAE"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": []},
                {"id": "branch_a", "kind": "branch", "nodes": [["", "sample-a"], ["", "decode-a"]]},
                {"id": "branch_b", "kind": "branch", "nodes": [["", "sample-b"], ["", "decode-b"]]},
            ],
            "shared_nodes": [{"node": ["", "checkpoint"], "home": "loaders"}],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    assert _node_sections(result)["checkpoint"] == "loaders"
    assert [ref.uid for ref in _groups_by_id(result)["loaders"].node_refs] == ["checkpoint"]
    layouts = _layouts_by_uid(result)
    assert layouts["checkpoint"].x < layouts["sample-a"].x == layouts["sample-b"].x
    assert layouts["sample-a"].x == layouts["decode-a"].x
    assert layouts["sample-b"].x == layouts["decode-b"].x
    assert layouts["sample-a"].y < layouts["decode-a"].y
    assert layouts["sample-b"].y < layouts["decode-b"].y


def test_compile_layout_plan_uses_deterministic_cluster_grid_for_huge_sections() -> None:
    node_count = COMPILE_HUGE_WORKFLOW_NODE_THRESHOLD + 4
    nodes = []
    links = []
    for index in range(node_count):
        node_id = index + 1
        uid = f"chain-{index:02d}"
        inputs = [{"name": "in", "type": "*", "link": 100 + index - 1}] if index > 0 else None
        outputs = [{"name": "out", "type": "*", "links": [100 + index]}] if index < node_count - 1 else None
        nodes.append(_with_io(_node(node_id, "PrimitiveNode", uid), inputs=inputs, outputs=outputs))
        if index < node_count - 1:
            links.append([100 + index, node_id, 0, node_id + 1, 0, "*"])
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "huge",
                    "kind": "custom",
                    "nodes": [["", f"chain-{index:02d}"] for index in range(node_count)],
                }
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts({"nodes": nodes, "links": links}))

    assert result.ok is True
    assert _group_templates_by_id(result) == {"huge": "grid"}
    layouts = [_layouts_by_uid(result)[f"chain-{index:02d}"] for index in range(node_count)]
    assert {layout.x for layout in layouts[:COMPILE_LARGE_SECTION_CLUSTER_SIZE]} == {layouts[0].x}
    assert layouts[COMPILE_LARGE_SECTION_CLUSTER_SIZE].x > layouts[0].x
    assert layouts[COMPILE_LARGE_SECTION_CLUSTER_SIZE].y == layouts[0].y
    assert all(left.y < right.y for left, right in zip(layouts[:9], layouts[1:10]))
    assert compile_layout_plan(plan, extract_graph_facts({"nodes": nodes, "links": links})).to_json() == result.to_json()


def test_compile_layout_plan_anchors_set_get_reroute_and_note_helpers_without_group_ownership() -> None:
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "producer"), outputs=[{"name": "out", "type": "*", "links": [10, 12]}]),
            _with_io(_node(2, "SetNode", "set-helper"), inputs=[{"name": "in", "type": "*", "link": 10}]),
            _with_io(_node(3, "GetNode", "get-helper"), outputs=[{"name": "out", "type": "*", "links": [11]}]),
            _with_io(_node(4, "PrimitiveNode", "consumer"), inputs=[{"name": "in", "type": "*", "link": 11}]),
            _with_io(
                _node(5, "Reroute", "cross-reroute"),
                inputs=[{"name": "", "type": "*", "link": 12}],
                outputs=[{"name": "", "type": "*", "links": [13]}],
            ),
            _node(6, "MarkdownNote", "note-helper"),
        ],
        "links": [
            [10, 1, 0, 2, 0, "*"],
            [11, 3, 0, 4, 0, "*"],
            [12, 1, 0, 5, 0, "*"],
            [13, 5, 0, 4, 0, "*"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "producer_section", "kind": "custom", "nodes": [["", "producer"]]},
                {"id": "consumer_section", "kind": "custom", "nodes": [["", "consumer"]]},
            ],
            "helper_placements": [
                {"helper": ["", "set-helper"], "kind": "near-producer", "target": ["", "producer"]},
                {"helper": ["", "get-helper"], "kind": "near-consumer", "target": ["", "consumer"]},
                {
                    "helper": ["", "cross-reroute"],
                    "kind": "edge-path",
                    "from": ["", "producer"],
                    "to": ["", "consumer"],
                },
                {"helper": ["", "note-helper"], "kind": "inside-section", "section_id": "consumer_section"},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    sections = _node_sections(result)
    assert sections["set-helper"] == "producer_section"
    assert sections["get-helper"] == "consumer_section"
    assert sections["note-helper"] == "consumer_section"
    assert sections["cross-reroute"] == "__helpers__"
    layouts = _layouts_by_uid(result)
    assert layouts["producer"].x < layouts["set-helper"].x
    assert layouts["get-helper"].x < layouts["consumer"].x
    assert layouts["producer"].x < layouts["cross-reroute"].x < layouts["consumer"].x
    groups = _groups_by_id(result)
    assert "__helpers__" not in groups
    assert [ref.uid for ref in groups["producer_section"].node_refs] == ["producer"]
    assert [ref.uid for ref in groups["consumer_section"].node_refs] == ["consumer"]
    assert groups["consumer_section"].template == "notes_sidebar"
    assert groups["producer_section"].width > layouts["producer"].width


def test_compile_layout_plan_places_nested_subgraph_sections_before_parent_container() -> None:
    ui = {
        "nodes": [_node(1, "SubgraphContainer", "container")],
        "definitions": {
            "subgraphs": [
                {
                    "name": "Nested",
                    "nodes": [_node(1, "PrimitiveNode", "inner")],
                    "links": [],
                }
            ]
        },
    }
    facts = extract_graph_facts(ui)
    inner_ref = next(fact.ref for fact in facts.canonical_refs if fact.ref.uid == "inner")
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "parent", "kind": "container", "nodes": [["", "container"]]},
                {
                    "id": "child",
                    "kind": "custom",
                    "nodes": [inner_ref.to_json()],
                    "parent_id": "parent",
                },
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, facts)

    assert result.ok is True
    groups = _groups_by_id(result)
    assert groups["child"].scope_path == inner_ref.scope_path
    assert result.group_layouts[0].id == "child"
    assert groups["parent"].x <= groups["child"].x
    assert groups["parent"].y <= groups["child"].y
    assert groups["parent"].x + groups["parent"].width >= groups["child"].x + groups["child"].width
    assert groups["parent"].y + groups["parent"].height >= groups["child"].y + groups["child"].height


def test_compile_layout_plan_resolves_primary_collisions_with_gutters_and_containment() -> None:
    ui = {
        "nodes": [
            {
                **_with_io(
                    _node(1, "PrimitiveNode", "wide-source"),
                    outputs=[{"name": "out", "type": "*", "links": [10]}],
                ),
                "size": [760.4, 110.6],
            },
            {
                **_with_io(
                    _node(2, "PrimitiveNode", "wide-target"),
                    inputs=[{"name": "in", "type": "*", "link": 10}],
                ),
                "size": [760.4, 110.6],
            },
        ],
        "links": [[10, 1, 0, 2, 0, "*"]],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "source", "kind": "custom", "nodes": [["", "wide-source"]]},
                {"id": "target", "kind": "custom", "nodes": [["", "wide-target"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    layouts = _layouts_by_uid(result)
    source = layouts["wide-source"]
    target = layouts["wide-target"]
    assert not _rects_overlap_or_touch(source, target, gutter=32)
    assert not _rects_overlap_or_touch(_groups_by_id(result)["source"], _groups_by_id(result)["target"], gutter=32)
    assert target.x - source.x == 440
    assert target.y > source.y
    for group in result.group_layouts:
        for ref in group.node_refs:
            layout = layouts[ref.uid]
            assert group.x <= layout.x
            assert group.y + 36 <= layout.y
            assert group.x + group.width >= layout.x + layout.width
            assert group.y + group.height >= layout.y + layout.height
    assert [group.color for group in result.group_layouts] == ["#646464", "#646464"]
    assert compile_layout_plan(plan, extract_graph_facts(ui)).to_json() == result.to_json()


def test_compile_layout_plan_preserves_pinned_nodes_as_hard_collision_constraints() -> None:
    ui = {
        "nodes": [
            {**_node(1, "PrimitiveNode", "movable"), "pos": [48, 84], "size": [280, 100]},
            {**_node(2, "PrimitiveNode", "pinned"), "pos": [928, 84], "size": [280, 100]},
        ],
        "links": [],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "movable_section", "kind": "custom", "nodes": [["", "movable"]]},
                {"id": "pinned_section", "kind": "custom", "nodes": [["", "pinned"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(
        plan,
        extract_graph_facts(ui),
        options=LayoutCompileOptions(pinned_refs=(CanonicalNodeRef("", "pinned"),)),
    )

    layouts = _layouts_by_uid(result)
    assert layouts["pinned"].pinned is True
    assert (layouts["pinned"].x, layouts["pinned"].y) == (928, 84)
    assert layouts["movable"].y > layouts["pinned"].y
    assert not _rects_overlap_or_touch(layouts["movable"], layouts["pinned"], gutter=32)
    assert result.candidate_patch.to_json()["entries"]["pinned"]["pos"] == [928, 84]


def _rects_overlap_or_touch(left: object, right: object, *, gutter: int) -> bool:
    return not (
        left.x + left.width + gutter <= right.x
        or right.x + right.width + gutter <= left.x
        or left.y + left.height + gutter <= right.y
        or right.y + right.height + gutter <= left.y
    )


def test_compile_layout_plan_gate_metrics_pass_and_are_ordered() -> None:
    result = compile_layout_plan(_valid_plan(), extract_graph_facts(_ui()))

    assert result.report.verdict == "ok"
    assert result.report.issues == ()
    assert [metric.name for metric in result.metrics] == _expected_compile_metric_order()
    metrics = {metric.name: metric for metric in result.metrics}
    assert metrics[COMPILE_METRIC_NODE_OVERLAP_COUNT].value == 0
    assert metrics[COMPILE_METRIC_GROUP_OVERLAP_COUNT].value == 0
    assert metrics[COMPILE_METRIC_BACKWARD_EDGE_RATIO].value <= metrics[COMPILE_METRIC_BACKWARD_EDGE_RATIO].threshold
    assert metrics[COMPILE_METRIC_CROSSING_PROXY_COUNT].value == 0
    assert metrics[COMPILE_METRIC_MINIMUM_GUTTER].value >= metrics[COMPILE_METRIC_MINIMUM_GUTTER].threshold
    assert metrics[COMPILE_METRIC_HELPER_DISTANCE_MAX].value <= metrics[COMPILE_METRIC_HELPER_DISTANCE_MAX].threshold
    assert metrics[COMPILE_METRIC_IDEMPOTENCE_DELTA].value == 0


def test_compile_layout_plan_gate_failure_report_orders_actionable_details() -> None:
    ref_a = CanonicalNodeRef("", "a")
    ref_b = CanonicalNodeRef("", "b")
    ref_c = CanonicalNodeRef("", "c")
    ref_d = CanonicalNodeRef("", "d")
    ref_e = CanonicalNodeRef("", "e")
    ref_f = CanonicalNodeRef("", "f")
    ref_helper = CanonicalNodeRef("", "helper")
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "a"), outputs=[{"name": "out", "type": "*", "links": [10, 12]}]),
            _with_io(_node(2, "PrimitiveNode", "b"), inputs=[{"name": "in", "type": "*", "link": 10}]),
            _with_io(_node(3, "PrimitiveNode", "c"), outputs=[{"name": "out", "type": "*", "links": [11]}]),
            _with_io(_node(4, "PrimitiveNode", "d"), inputs=[{"name": "in", "type": "*", "link": 11}]),
            _node(5, "PrimitiveNode", "e"),
            _node(6, "PrimitiveNode", "f"),
            _with_io(_node(7, "Reroute", "helper"), inputs=[{"name": "in", "type": "*", "link": 12}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "*"],
            [11, 3, 0, 4, 0, "*"],
            [12, 1, 0, 7, 0, "*"],
        ],
    }
    sidecar = {
        "schema_hash": LayoutCandidatePatch().schema_hash,
        "reorganise_compiler": True,
        "entries": {
            uid: {"pos": [0, 0], "size": [1, 1]}
            for uid in ("a", "b", "c", "d", "e", "f", "helper")
        },
        "groups": [
            {"title": "Left", "bounding": [0, 0, 1, 1], "nodes": ["a", "b"]},
            {"title": "Right", "bounding": [0, 0, 1, 1], "nodes": ["c", "d"]},
        ],
    }
    facts = extract_graph_facts(ui, sidecar_envelope=sidecar)
    node_layouts = (
        CompiledNodeLayout(ref=ref_a, section_id="left", role_hint=ROLE_HINT_UNKNOWN, x=320, y=0),
        CompiledNodeLayout(ref=ref_b, section_id="left", role_hint=ROLE_HINT_UNKNOWN, x=0, y=320),
        CompiledNodeLayout(ref=ref_c, section_id="right", role_hint=ROLE_HINT_UNKNOWN, x=80, y=160),
        CompiledNodeLayout(ref=ref_d, section_id="right", role_hint=ROLE_HINT_UNKNOWN, x=420, y=320),
        CompiledNodeLayout(ref=ref_e, section_id="overlap", role_hint=ROLE_HINT_UNKNOWN, x=720, y=0),
        CompiledNodeLayout(ref=ref_f, section_id="overlap", role_hint=ROLE_HINT_UNKNOWN, x=740, y=10),
        CompiledNodeLayout(ref=ref_helper, section_id="__helpers__", role_hint=ROLE_HINT_HELPER, x=2000, y=2000),
    )
    group_layouts = (
        CompiledGroupLayout(
            id="left",
            scope_path="",
            title="Left",
            kind="custom",
            node_refs=(ref_a, ref_b),
            x=0,
            y=0,
            width=250,
            height=250,
            color="#646464",
        ),
        CompiledGroupLayout(
            id="right",
            scope_path="",
            title="Right",
            kind="custom",
            node_refs=(ref_c, ref_d),
            x=100,
            y=100,
            width=250,
            height=250,
            color="#646464",
        ),
    )
    candidate_patch = LayoutCandidatePatch(
        entries={
            layout.ref.uid: {"pos": [layout.x, layout.y], "size": [layout.width, layout.height]}
            for layout in node_layouts
        },
        groups=(
            {"title": "Left", "bounding": [0, 0, 250, 250], "nodes": ["a", "b"]},
            {"title": "Right", "bounding": [100, 100, 250, 250], "nodes": ["c", "d"]},
        ),
    )

    report = _build_report(
        node_layouts=node_layouts,
        group_layouts=group_layouts,
        facts=facts,
        candidate_patch=candidate_patch,
        structural_hash_before="before",
        structural_hash_after="after",
        diagnostics=(),
    )

    assert report.verdict == "blocked"
    assert [metric.name for metric in report.metrics] == _expected_compile_metric_order()
    assert [issue.code for issue in report.issues] == [
        COMPILE_ISSUE_NODE_OVERLAP,
        COMPILE_ISSUE_GROUP_OVERLAP,
        COMPILE_ISSUE_BACKWARD_EDGE_RATIO_HIGH,
        COMPILE_ISSUE_CROSSING_PROXY_HIGH,
        COMPILE_ISSUE_MINIMUM_GUTTER,
        COMPILE_ISSUE_HELPER_DISTANCE_HIGH,
        COMPILE_ISSUE_IDEMPOTENCE_DELTA,
        "compiler_structural_hash_changed",
    ]
    issues = {issue.code: issue.to_json() for issue in report.issues}
    assert issues[COMPILE_ISSUE_NODE_OVERLAP]["detail"]["pairs"] == [[["", "e"], ["", "f"]]]
    assert issues[COMPILE_ISSUE_GROUP_OVERLAP]["detail"]["pairs"][0][0]["id"] == "left"
    assert issues[COMPILE_ISSUE_GROUP_OVERLAP]["detail"]["pairs"][0][1]["id"] == "right"
    assert issues[COMPILE_ISSUE_CROSSING_PROXY_HIGH]["detail"]["edge_pairs"][0][0]["source"] == ["", "a"]
    assert issues[COMPILE_ISSUE_CROSSING_PROXY_HIGH]["detail"]["edge_pairs"][0][0]["target"] == ["", "b"]
    assert issues[COMPILE_ISSUE_MINIMUM_GUTTER]["detail"]["violations"][0]["kind"] in {"group", "node"}
    assert issues[COMPILE_ISSUE_HELPER_DISTANCE_HIGH]["detail"]["violations"][0]["helper_ref"] == ["", "helper"]
    assert issues[COMPILE_ISSUE_IDEMPOTENCE_DELTA]["detail"]["measured"] is True
    assert issues["compiler_structural_hash_changed"]["detail"] == {"before": "before", "after": "after"}


def _expected_compile_metric_order() -> list[str]:
    return [
        "compiled_node_layout_count",
        "compiled_group_layout_count",
        "compiled_helper_layout_count",
        COMPILE_METRIC_NODE_OVERLAP_COUNT,
        COMPILE_METRIC_GROUP_OVERLAP_COUNT,
        COMPILE_METRIC_BACKWARD_EDGE_RATIO,
        COMPILE_METRIC_CROSSING_PROXY_COUNT,
        COMPILE_METRIC_MINIMUM_GUTTER,
        COMPILE_METRIC_HELPER_DISTANCE_MAX,
        COMPILE_METRIC_IDEMPOTENCE_DELTA,
        COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED,
    ]
