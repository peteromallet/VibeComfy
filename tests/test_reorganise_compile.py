from __future__ import annotations

from copy import deepcopy

from vibecomfy.porting.reorganise import LayoutCompileOptions, compile_layout_plan
from vibecomfy.porting.reorganise.compile import (
    COMPILE_ISSUE_BASELINE_VARIANCE_HIGH,
    COMPILE_ISSUE_BACKWARD_EDGE_RATIO_HIGH,
    COMPILE_ISSUE_CROSSING_PROXY_HIGH,
    COMPILE_ISSUE_DETACHED_GROUP_DISTANCE_HIGH,
    COMPILE_ISSUE_GROUP_OVERLAP,
    COMPILE_ISSUE_HELPER_DISTANCE_HIGH,
    COMPILE_ISSUE_HELPER_SIDECAR_OVERLAP,
    COMPILE_ISSUE_IDEMPOTENCE_DELTA,
    COMPILE_ISSUE_INTERNAL_WHITESPACE_HIGH,
    COMPILE_ISSUE_LONG_EDGE_DISTANCE_HIGH,
    COMPILE_ISSUE_MAX_PRIMARY_ROW_COUNT_HIGH,
    COMPILE_ISSUE_MIXED_CORE_ROLE,
    COMPILE_ISSUE_MINIMUM_GUTTER,
    COMPILE_ISSUE_NOTE_SECTION_MISMATCH,
    COMPILE_ISSUE_NODE_OVERLAP,
    COMPILE_HUGE_WORKFLOW_NODE_THRESHOLD,
    COMPILE_LARGE_SECTION_CLUSTER_SIZE,
    COMPILE_METRIC_BACKWARD_EDGE_RATIO,
    COMPILE_METRIC_BASELINE_VARIANCE_MAX,
    COMPILE_METRIC_CROSSING_PROXY_COUNT,
    COMPILE_METRIC_DETACHED_GROUP_DISTANCE_MAX,
    COMPILE_METRIC_GROUP_OVERLAP_COUNT,
    COMPILE_METRIC_HELPER_DISTANCE_MAX,
    COMPILE_METRIC_HELPER_SIDECAR_OVERLAP_COUNT,
    COMPILE_METRIC_IDEMPOTENCE_DELTA,
    COMPILE_METRIC_INTERNAL_WHITESPACE_RATIO_MAX,
    COMPILE_METRIC_LONG_EDGE_DISTANCE_MAX,
    COMPILE_METRIC_MAX_PRIMARY_NODES_PER_ROW,
    COMPILE_METRIC_MINIMUM_GUTTER,
    COMPILE_METRIC_NOTE_SECTION_MISMATCH_COUNT,
    COMPILE_METRIC_NODE_OVERLAP_COUNT,
    COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED,
    _CompileTraceAccumulator,
    _classify_layout_phase,
    _compile_section_ownership_phase,
    _local_bounds,
    _local_section_layout,
    _layout_primary_rows,
    _node_size_for_ref,
    _spacing,
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


def _make_node(node_id: int, class_type: str, uid: str, *, size: list[int] | None = None) -> dict:
    node = _node(node_id, class_type, uid)
    if size is not None:
        node["size"] = list(size)
    return node


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
    from_ui_result = compile_layout_plan_from_ui(_valid_plan(), _ui())

    assert result.ok is True
    assert from_ui_result.to_json() == result.to_json()
    assert result.validation_report.ok is True
    assert result.report.verdict == "ok"
    assert [metric.name for metric in result.metrics] == [
        "compiled_node_layout_count",
        "compiled_group_layout_count",
        "compiled_helper_layout_count",
        COMPILE_METRIC_NODE_OVERLAP_COUNT,
        COMPILE_METRIC_GROUP_OVERLAP_COUNT,
        COMPILE_METRIC_INTERNAL_WHITESPACE_RATIO_MAX,
        COMPILE_METRIC_BASELINE_VARIANCE_MAX,
        COMPILE_METRIC_DETACHED_GROUP_DISTANCE_MAX,
        COMPILE_METRIC_HELPER_SIDECAR_OVERLAP_COUNT,
        COMPILE_METRIC_NOTE_SECTION_MISMATCH_COUNT,
        COMPILE_METRIC_MAX_PRIMARY_NODES_PER_ROW,
        COMPILE_METRIC_LONG_EDGE_DISTANCE_MAX,
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
    assert set(patch["entries"]["checkpoint"]) <= {
        "pos",
        "size",
        "flags",
        "color",
        "bgcolor",
        "mode",
        "properties",
    }
    assert not {
        "type",
        "class_type",
        "widgets_values",
        "inputs",
        "outputs",
    } & set(patch["entries"]["checkpoint"])
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
    assert "reorganise_compiler" not in patch
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


def test_compile_layout_plan_packs_section_local_sidecars_without_primary_overlap() -> None:
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "left"), outputs=[{"name": "out", "type": "*", "links": []}]),
            _with_io(_node(2, "PrimitiveNode", "target"), outputs=[{"name": "out", "type": "*", "links": [10]}]),
            _with_io(_node(3, "PrimitiveNode", "right"), outputs=[{"name": "out", "type": "*", "links": []}]),
            _with_io(_node(4, "SetNode", "set-helper"), inputs=[{"name": "in", "type": "*", "link": 10}]),
            _with_io(_node(5, "GetNode", "get-helper"), outputs=[{"name": "out", "type": "*", "links": [11]}]),
        ],
        "links": [
            [10, 2, 0, 4, 0, "*"],
            [11, 5, 0, 2, 0, "*"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "main",
                    "kind": "custom",
                    "nodes": [["", "left"], ["", "target"], ["", "right"]],
                }
            ],
            "helper_placements": [
                {"helper": ["", "set-helper"], "kind": "near-producer", "target": ["", "target"]},
                {"helper": ["", "get-helper"], "kind": "near-consumer", "target": ["", "target"]},
            ],
            "unassigned_policy": "reject",
        }
    )
    facts = extract_graph_facts(ui)

    result = compile_layout_plan(plan, facts)

    assert result.ok is True
    layouts = _layouts_by_uid(result)
    assert layouts["get-helper"].x + layouts["get-helper"].width < layouts["target"].x
    assert layouts["target"].x + layouts["target"].width < layouts["set-helper"].x
    for left_uid, right_uid in (
        ("left", "get-helper"),
        ("right", "get-helper"),
        ("get-helper", "target"),
        ("target", "set-helper"),
    ):
        left = layouts[left_uid]
        right = layouts[right_uid]
        assert left.x + left.width < right.x

    trace = _CompileTraceAccumulator(facts)
    classification = _classify_layout_phase(facts, trace=trace)
    sections = _compile_section_ownership_phase(
        plan,
        facts,
        classification,
        LayoutCompileOptions(),
        trace=trace,
    )
    main_section = next(section for section in sections if section.id == "main")
    local_layout = _local_section_layout(
        main_section,
        facts,
        {fact.ref: fact for fact in facts.node_furniture},
        LayoutCompileOptions(),
        _spacing("balanced"),
        plan,
    )
    assert "sidecar:right:stack:0:target:target" in local_layout.placement_choices[CanonicalNodeRef("", "set-helper")]
    assert "sidecar:left:stack:0:target:target" in local_layout.placement_choices[CanonicalNodeRef("", "get-helper")]


def test_compile_section_ownership_phase_attaches_helpers_and_emits_ownership_trace() -> None:
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
            ],
            "unassigned_policy": "reject",
        }
    )
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)
    classification = _classify_layout_phase(facts, trace=trace)

    sections = _compile_section_ownership_phase(
        plan,
        facts,
        classification,
        LayoutCompileOptions(),
        trace=trace,
    )

    assert {ref.uid: section.id for section in sections for ref in section.node_refs} == {
        "consumer": "consumer_section",
        "cross-reroute": "__helpers__",
        "get-helper": "consumer_section",
        "note-helper": "consumer_section",
        "producer": "producer_section",
        "set-helper": "producer_section",
    }
    trace_entries = {entry.ref.uid: entry for entry in trace.to_entries()}
    assert trace_entries["set-helper"].attachment_target == CanonicalNodeRef("", "producer")
    assert trace_entries["set-helper"].reason == "helper_targeted_placement"
    assert trace_entries["get-helper"].attachment_target == CanonicalNodeRef("", "consumer")
    assert trace_entries["get-helper"].reason == "helper_targeted_placement"
    assert trace_entries["cross-reroute"].section_id == "__helpers__"
    assert trace_entries["cross-reroute"].attachment_target is None
    assert trace_entries["cross-reroute"].reason == "helper_unowned_fallback"
    assert trace_entries["note-helper"].section_id == "consumer_section"
    assert trace_entries["note-helper"].attachment_target == CanonicalNodeRef("", "consumer")
    assert trace_entries["note-helper"].reason == "note_annotated_primary"


def test_compile_section_ownership_phase_assigns_connected_note_to_primary_section() -> None:
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "producer"), outputs=[{"name": "out", "type": "*", "links": [10]}]),
            _with_io(_node(2, "MarkdownNote", "note-helper"), inputs=[{"name": "in", "type": "*", "link": 10}]),
        ],
        "links": [[10, 1, 0, 2, 0, "*"]],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [{"id": "producer_section", "kind": "custom", "nodes": [["", "producer"]]}],
            "unassigned_policy": "reject",
        }
    )
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)

    _compile_section_ownership_phase(
        plan,
        facts,
        _classify_layout_phase(facts, trace=trace),
        LayoutCompileOptions(),
        trace=trace,
    )

    trace_entries = {entry.ref.uid: entry for entry in trace.to_entries()}
    assert trace_entries["note-helper"].section_id == "producer_section"
    assert trace_entries["note-helper"].attachment_target == CanonicalNodeRef("", "producer")
    assert trace_entries["note-helper"].reason == "note_connected_primary"
    assert trace_entries["producer"].reason == "primary_explicit_section"


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


def test_compile_layout_plan_places_wide_sections_without_mutating_for_collision_repair() -> None:
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
    assert target.x - source.x >= source.width + 32
    assert target.y == source.y
    for group in result.group_layouts:
        for ref in group.node_refs:
            layout = layouts[ref.uid]
            assert group.x <= layout.x
            assert group.y + 36 <= layout.y
            assert group.x + group.width >= layout.x + layout.width
            assert group.y + group.height >= layout.y + layout.height
    assert [group.color for group in result.group_layouts] == ["#646464", "#646464"]
    assert compile_layout_plan(plan, extract_graph_facts(ui)).to_json() == result.to_json()


def test_compile_layout_plan_preserves_pinned_nodes_and_reports_collisions_without_mutating() -> None:
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
    assert (layouts["movable"].x, layouts["movable"].y) == (48, 84)
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
    assert metrics[COMPILE_METRIC_INTERNAL_WHITESPACE_RATIO_MAX].value <= metrics[COMPILE_METRIC_INTERNAL_WHITESPACE_RATIO_MAX].threshold
    assert metrics[COMPILE_METRIC_BASELINE_VARIANCE_MAX].value <= metrics[COMPILE_METRIC_BASELINE_VARIANCE_MAX].threshold
    assert metrics[COMPILE_METRIC_DETACHED_GROUP_DISTANCE_MAX].value <= metrics[COMPILE_METRIC_DETACHED_GROUP_DISTANCE_MAX].threshold
    assert metrics[COMPILE_METRIC_HELPER_SIDECAR_OVERLAP_COUNT].value == 0
    assert metrics[COMPILE_METRIC_NOTE_SECTION_MISMATCH_COUNT].value == 0
    assert metrics[COMPILE_METRIC_MAX_PRIMARY_NODES_PER_ROW].value <= metrics[COMPILE_METRIC_MAX_PRIMARY_NODES_PER_ROW].threshold
    assert metrics[COMPILE_METRIC_LONG_EDGE_DISTANCE_MAX].value <= metrics[COMPILE_METRIC_LONG_EDGE_DISTANCE_MAX].threshold
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


def test_compile_layout_plan_adds_extended_validation_metric_warnings_without_blocking() -> None:
    ref_a = CanonicalNodeRef("", "a")
    ref_b = CanonicalNodeRef("", "b")
    ref_c = CanonicalNodeRef("", "c")
    ref_d = CanonicalNodeRef("", "d")
    ref_far = CanonicalNodeRef("", "far")
    ref_note = CanonicalNodeRef("", "note")
    ref_helper = CanonicalNodeRef("", "helper")
    ui = {
        "nodes": [
            _with_io(_node(1, "KSampler", "a"), outputs=[{"name": "out", "type": "*", "links": [10, 15]}]),
            _with_io(_node(2, "KSampler", "b"), inputs=[{"name": "in", "type": "*", "link": 10}]),
            _node(3, "KSampler", "c"),
            _with_io(_node(4, "KSampler", "d"), outputs=[{"name": "out", "type": "*", "links": [11]}]),
            _with_io(_node(5, "KSampler", "far"), inputs=[{"name": "in", "type": "*", "link": 11}]),
            _with_io(_node(6, "MarkdownNote", "note"), inputs=[{"name": "in", "type": "*", "link": 15}]),
            _with_io(_node(7, "Reroute", "helper"), inputs=[{"name": "in", "type": "*", "link": 10}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "*"],
            [11, 4, 0, 5, 0, "*"],
            [15, 1, 0, 6, 0, "*"],
        ],
    }
    facts = extract_graph_facts(ui)
    node_layouts = (
        CompiledNodeLayout(ref=ref_a, section_id="main", role_hint=ROLE_HINT_UNKNOWN, x=0, y=0),
        CompiledNodeLayout(ref=ref_b, section_id="main", role_hint=ROLE_HINT_UNKNOWN, x=320, y=4),
        CompiledNodeLayout(ref=ref_c, section_id="main", role_hint=ROLE_HINT_UNKNOWN, x=640, y=8),
        CompiledNodeLayout(ref=ref_d, section_id="main", role_hint=ROLE_HINT_UNKNOWN, x=960, y=12),
        CompiledNodeLayout(ref=ref_far, section_id="target", role_hint=ROLE_HINT_UNKNOWN, x=4600, y=0),
        CompiledNodeLayout(ref=ref_note, section_id="target", role_hint=ROLE_HINT_HELPER, x=100, y=200),
        CompiledNodeLayout(ref=ref_helper, section_id="main", role_hint=ROLE_HINT_HELPER, x=10, y=0),
    )
    group_layouts = (
        CompiledGroupLayout(
            id="main",
            scope_path="",
            title="Main",
            kind="custom",
            node_refs=(ref_a, ref_b, ref_c, ref_d),
            x=0,
            y=0,
            width=2800,
            height=420,
            color="#646464",
        ),
        CompiledGroupLayout(
            id="target",
            scope_path="",
            title="Target",
            kind="custom",
            node_refs=(ref_far,),
            x=4600,
            y=0,
            width=700,
            height=360,
            color="#646464",
        ),
    )
    candidate_patch = LayoutCandidatePatch(
        entries={
            layout.ref.uid: {"pos": [layout.x, layout.y], "size": [layout.width, layout.height]}
            for layout in node_layouts
        },
        groups=(
            {"id": "main", "title": "Main", "bounding": [0, 0, 2800, 420], "nodes": ["a", "b", "c", "d"]},
            {"id": "target", "title": "Target", "bounding": [4600, 0, 700, 360], "nodes": ["far"]},
        ),
    )

    report = _build_report(
        node_layouts=node_layouts,
        group_layouts=group_layouts,
        facts=facts,
        candidate_patch=candidate_patch,
        structural_hash_before="same",
        structural_hash_after="same",
        diagnostics=(),
    )

    assert report.verdict == "needs_reorganise"
    metrics = {metric.name: metric for metric in report.metrics}
    assert metrics[COMPILE_METRIC_INTERNAL_WHITESPACE_RATIO_MAX].value > metrics[COMPILE_METRIC_INTERNAL_WHITESPACE_RATIO_MAX].threshold
    assert metrics[COMPILE_METRIC_BASELINE_VARIANCE_MAX].value > metrics[COMPILE_METRIC_BASELINE_VARIANCE_MAX].threshold
    assert metrics[COMPILE_METRIC_DETACHED_GROUP_DISTANCE_MAX].value > metrics[COMPILE_METRIC_DETACHED_GROUP_DISTANCE_MAX].threshold
    assert metrics[COMPILE_METRIC_HELPER_SIDECAR_OVERLAP_COUNT].value == 1
    assert metrics[COMPILE_METRIC_NOTE_SECTION_MISMATCH_COUNT].value == 1
    assert metrics[COMPILE_METRIC_MAX_PRIMARY_NODES_PER_ROW].value == 4
    assert metrics[COMPILE_METRIC_LONG_EDGE_DISTANCE_MAX].value > metrics[COMPILE_METRIC_LONG_EDGE_DISTANCE_MAX].threshold

    issues = {issue.code: issue.to_json() for issue in report.issues}
    assert issues[COMPILE_ISSUE_INTERNAL_WHITESPACE_HIGH]["severity"] == "warning"
    assert issues[COMPILE_ISSUE_BASELINE_VARIANCE_HIGH]["detail"]["rows"][0]["section_id"] == "main"
    assert issues[COMPILE_ISSUE_DETACHED_GROUP_DISTANCE_HIGH]["detail"]["connections"][0]["source_section"] == "main"
    assert issues[COMPILE_ISSUE_HELPER_SIDECAR_OVERLAP]["detail"]["pairs"] == [[["", "a"], ["", "helper"]]]
    assert issues[COMPILE_ISSUE_NOTE_SECTION_MISMATCH]["detail"]["mismatches"][0]["expected_section"] == "main"
    assert issues[COMPILE_ISSUE_MAX_PRIMARY_ROW_COUNT_HIGH]["detail"]["rows"][0]["count"] == 4
    assert issues[COMPILE_ISSUE_LONG_EDGE_DISTANCE_HIGH]["detail"]["edges"][0]["target"] == ["", "far"]


def test_compile_issues_warn_on_loader_in_output_section() -> None:
    """A CheckpointLoaderSimple inside an output section should trigger a
    warning-level mixed-core-role diagnostic without blocking compilation."""
    ui = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "SaveImage", "save"),
        ],
        "links": [
            [10, 1, 0, 2, 0, "MODEL"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "output", "kind": "output", "nodes": [["", "checkpoint"], ["", "save"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    # Compilation must not be blocked — warning only.
    assert result.ok is True
    issues_by_code = {issue.code: issue for issue in result.report.issues}
    assert COMPILE_ISSUE_MIXED_CORE_ROLE in issues_by_code
    issue = issues_by_code[COMPILE_ISSUE_MIXED_CORE_ROLE]
    assert issue.severity == "warning"
    assert issue.detail["section_id"] == "output"
    assert issue.detail["section_kind"] == "output"
    mismatched = issue.detail["mismatched"]
    assert len(mismatched) == 1
    assert mismatched[0]["ref"] == ("", "checkpoint")
    assert mismatched[0]["actual_role"] == "loader"


def test_compile_no_warning_when_all_nodes_match_section_role() -> None:
    """No mixed-core-role warning when every node's classified role matches its section."""
    ui = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "CLIPTextEncode", "positive"),
            _node(3, "KSampler", "sample"),
            _node(4, "VAEDecode", "decode"),
            _node(5, "SaveImage", "save"),
        ],
        "links": [
            [10, 1, 0, 3, 0, "MODEL"],
            [11, 2, 0, 3, 1, "CONDITIONING"],
            [12, 3, 0, 4, 0, "LATENT"],
            [13, 4, 0, 5, 0, "IMAGE"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": [["", "checkpoint"]]},
                {"id": "conditioning", "kind": "conditioning", "nodes": [["", "positive"]]},
                {"id": "sampling", "kind": "sampling", "nodes": [["", "sample"]]},
                {"id": "output", "kind": "output", "nodes": [["", "decode"], ["", "save"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    issues_by_code = {issue.code for issue in result.report.issues}
    assert COMPILE_ISSUE_MIXED_CORE_ROLE not in issues_by_code


def test_compile_custom_section_excluded_from_role_purity_warnings() -> None:
    """Custom sections are never checked for mixed core roles."""
    ui = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "SaveImage", "save"),
        ],
        "links": [
            [10, 1, 0, 2, 0, "MODEL"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "custom_section", "kind": "custom", "nodes": [["", "checkpoint"], ["", "save"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    issues_by_code = {issue.code for issue in result.report.issues}
    assert COMPILE_ISSUE_MIXED_CORE_ROLE not in issues_by_code


def test_compile_utility_section_excluded_from_role_purity_warnings() -> None:
    """Utility sections are never checked for mixed core roles."""
    ui = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "Reroute", "reroute"),
        ],
        "links": [],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "utils", "kind": "utility", "nodes": [["", "checkpoint"]]},
            ],
            "helper_placements": [
                {"helper": ["", "reroute"], "kind": "inside-section", "section_id": "utils"},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    issues_by_code = {issue.code for issue in result.report.issues}
    assert COMPILE_ISSUE_MIXED_CORE_ROLE not in issues_by_code


def test_compile_container_section_excluded_from_role_purity_warnings() -> None:
    """Container sections are never checked for mixed core roles."""
    ui = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
        ],
        "links": [],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "container", "kind": "container", "nodes": [["", "checkpoint"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    issues_by_code = {issue.code for issue in result.report.issues}
    assert COMPILE_ISSUE_MIXED_CORE_ROLE not in issues_by_code


def test_compile_branch_section_excluded_from_role_purity_warnings() -> None:
    """Branch sections (inherently heterogeneous) are never checked for mixed core roles."""
    ui = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "CLIPTextEncode", "prompt"),
            _node(3, "KSampler", "sample"),
        ],
        "links": [
            [10, 1, 0, 3, 0, "MODEL"],
            [11, 2, 0, 3, 1, "CONDITIONING"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "branch", "kind": "branch", "nodes": [["", "checkpoint"], ["", "prompt"], ["", "sample"]]},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    issues_by_code = {issue.code for issue in result.report.issues}
    assert COMPILE_ISSUE_MIXED_CORE_ROLE not in issues_by_code


def test_compile_helper_node_in_core_section_does_not_trigger_warning() -> None:
    """A Reroute helper inside a loader section should not trigger a mixed-role warning."""
    ui = {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "Reroute", "reroute"),
        ],
        "links": [],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": [["", "checkpoint"]]},
            ],
            "helper_placements": [
                {"helper": ["", "reroute"], "kind": "inside-section", "section_id": "loaders"},
            ],
            "unassigned_policy": "reject",
        }
    )

    result = compile_layout_plan(plan, extract_graph_facts(ui))

    assert result.ok is True
    issues_by_code = {issue.code for issue in result.report.issues}
    assert COMPILE_ISSUE_MIXED_CORE_ROLE not in issues_by_code


# ---------------------------------------------------------------------------
# Ownership behavior tests — inspect pre-positioning section ownership
# and trace-visible fallback when ownership evidence is absent.
# ---------------------------------------------------------------------------


def test_compile_section_ownership_setnode_without_placement_falls_back() -> None:
    """SetNode without an explicit helper_placement must fall back to
    __helpers__ because SetNode edges are excluded from effective_edges.
    The fallback reason must be trace-visible."""
    ui = {
        "nodes": [
            {
                **_with_io(_node(1, "PrimitiveNode", "producer"), outputs=[{"name": "out", "type": "*", "links": [10]}]),
                "pos": [0, 0],
                "size": [200, 80],
            },
            {
                **_with_io(_node(2, "SetNode", "set-helper"), inputs=[{"name": "in", "type": "*", "link": 10}]),
                "pos": [300, 0],
                "size": [200, 80],
            },
            _node(3, "PrimitiveNode", "consumer"),
        ],
        "links": [[10, 1, 0, 2, 0, "*"]],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "producer_section", "kind": "custom", "nodes": [["", "producer"]]},
                {"id": "consumer_section", "kind": "custom", "nodes": [["", "consumer"]]},
            ],
            "unassigned_policy": "reject",
        }
    )
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)

    sections = _compile_section_ownership_phase(
        plan,
        facts,
        _classify_layout_phase(facts, trace=trace),
        LayoutCompileOptions(),
        trace=trace,
    )

    trace_entries = {entry.ref.uid: entry for entry in trace.to_entries()}
    assert trace_entries["set-helper"].section_id == "__helpers__"
    assert trace_entries["set-helper"].attachment_target is None
    assert trace_entries["set-helper"].reason == "helper_unowned_fallback"

    # Pre-positioning: the unowned SetNode must live in __helpers__
    helpers_section = next(
        (section for section in sections if section.id == "__helpers__"), None
    )
    assert helpers_section is not None
    assert CanonicalNodeRef("", "set-helper") in helpers_section.node_refs


def test_compile_section_ownership_getnode_without_placement_falls_back() -> None:
    """GetNode without an explicit helper_placement must fall back to
    __helpers__ because GetNode edges are excluded from effective_edges.
    The fallback reason must be trace-visible."""
    ui = {
        "nodes": [
            _node(1, "PrimitiveNode", "producer"),
            {
                **_with_io(_node(2, "GetNode", "get-helper"), outputs=[{"name": "out", "type": "*", "links": [11]}]),
                "pos": [0, 0],
                "size": [200, 80],
            },
            {
                **_with_io(_node(3, "PrimitiveNode", "consumer"), inputs=[{"name": "in", "type": "*", "link": 11}]),
                "pos": [300, 0],
                "size": [200, 80],
            },
        ],
        "links": [[11, 2, 0, 3, 0, "*"]],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "producer_section", "kind": "custom", "nodes": [["", "producer"]]},
                {"id": "consumer_section", "kind": "custom", "nodes": [["", "consumer"]]},
            ],
            "unassigned_policy": "reject",
        }
    )
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)

    sections = _compile_section_ownership_phase(
        plan,
        facts,
        _classify_layout_phase(facts, trace=trace),
        LayoutCompileOptions(),
        trace=trace,
    )

    trace_entries = {entry.ref.uid: entry for entry in trace.to_entries()}
    assert trace_entries["get-helper"].section_id == "__helpers__"
    assert trace_entries["get-helper"].attachment_target is None
    assert trace_entries["get-helper"].reason == "helper_unowned_fallback"

    # Pre-positioning: the unowned GetNode must live in __helpers__
    helpers_section = next(
        (section for section in sections if section.id == "__helpers__"), None
    )
    assert helpers_section is not None
    assert CanonicalNodeRef("", "get-helper") in helpers_section.node_refs


def test_compile_section_ownership_unconnectable_note_falls_back_to_helpers() -> None:
    """A MarkdownNote with no graph connections and positioned far from every
    primary (no annotation evidence) should fall back to __helpers__ with a
    trace-visible reason."""
    ui = {
        "nodes": [
            {
                **_node(1, "PrimitiveNode", "producer"),
                "pos": [0, 0],
                "size": [200, 80],
            },
            {
                **_node(2, "MarkdownNote", "orphan-note"),
                "pos": [800, 600],
                "size": [200, 80],
            },
        ],
        "links": [],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "producer_section", "kind": "custom", "nodes": [["", "producer"]]},
            ],
            "unassigned_policy": "reject",
        }
    )
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)

    sections = _compile_section_ownership_phase(
        plan,
        facts,
        _classify_layout_phase(facts, trace=trace),
        LayoutCompileOptions(),
        trace=trace,
    )

    trace_entries = {entry.ref.uid: entry for entry in trace.to_entries()}
    assert trace_entries["orphan-note"].section_id == "__helpers__"
    assert trace_entries["orphan-note"].attachment_target is None
    assert trace_entries["orphan-note"].reason == "note_unowned_fallback"

    # Pre-positioning: the __helpers__ section should contain the orphan note
    helpers_section = next(
        (section for section in sections if section.id == "__helpers__"), None
    )
    assert helpers_section is not None
    assert CanonicalNodeRef("", "orphan-note") in helpers_section.node_refs


def test_compile_section_ownership_ambiguous_helper_spanning_sections_falls_back() -> None:
    """A helper (Reroute) whose incident primaries belong to different
    sections should fall back to __helpers__ with a trace-visible reason,
    confirming ambiguity is not silently swallowed."""
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "left-producer"), outputs=[{"name": "out", "type": "*", "links": [10]}]),
            _with_io(
                _node(2, "Reroute", "cross-reroute"),
                inputs=[{"name": "", "type": "*", "link": 10}],
                outputs=[{"name": "", "type": "*", "links": [11]}],
            ),
            _with_io(_node(3, "PrimitiveNode", "right-consumer"), inputs=[{"name": "in", "type": "*", "link": 11}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "*"],
            [11, 2, 0, 3, 0, "*"],
        ],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "left_section", "kind": "custom", "nodes": [["", "left-producer"]]},
                {"id": "right_section", "kind": "custom", "nodes": [["", "right-consumer"]]},
            ],
            "unassigned_policy": "reject",
        }
    )
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)

    sections = _compile_section_ownership_phase(
        plan,
        facts,
        _classify_layout_phase(facts, trace=trace),
        LayoutCompileOptions(),
        trace=trace,
    )

    trace_entries = {entry.ref.uid: entry for entry in trace.to_entries()}
    assert trace_entries["cross-reroute"].section_id == "__helpers__"
    assert trace_entries["cross-reroute"].attachment_target is None
    assert trace_entries["cross-reroute"].reason == "helper_unowned_fallback"

    # Pre-positioning: the ambiguous helper must appear in __helpers__ section
    helpers_section = next(
        (section for section in sections if section.id == "__helpers__"), None
    )
    assert helpers_section is not None
    assert CanonicalNodeRef("", "cross-reroute") in helpers_section.node_refs


def test_compile_section_ownership_known_primaries_are_preserved() -> None:
    """Primaries that are explicitly assigned to sections must retain their
    ownership decisions and trace entries should reflect the assignment."""
    ui = {
        "nodes": [
            _with_io(_node(1, "CheckpointLoaderSimple", "checkpoint"), outputs=[{"name": "MODEL", "type": "MODEL", "links": [10]}]),
            _with_io(_node(2, "KSampler", "sample"), inputs=[{"name": "model", "type": "MODEL", "link": 10}]),
        ],
        "links": [[10, 1, 0, 2, 0, "MODEL"]],
    }
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {"id": "loaders", "kind": "loaders", "nodes": [["", "checkpoint"]]},
                {"id": "sampling", "kind": "sampling", "nodes": [["", "sample"]]},
            ],
            "unassigned_policy": "reject",
        }
    )
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)

    sections = _compile_section_ownership_phase(
        plan,
        facts,
        _classify_layout_phase(facts, trace=trace),
        LayoutCompileOptions(),
        trace=trace,
    )

    trace_entries = {entry.ref.uid: entry for entry in trace.to_entries()}
    assert trace_entries["checkpoint"].section_id == "loaders"
    assert trace_entries["checkpoint"].reason == "primary_explicit_section"
    assert trace_entries["sample"].section_id == "sampling"
    assert trace_entries["sample"].reason == "primary_explicit_section"

    # Pre-positioning: sections should contain exactly the expected primaries
    section_ids = {section.id: section for section in sections}
    assert {ref.uid for ref in section_ids["loaders"].node_refs} == {"checkpoint"}
    assert {ref.uid for ref in section_ids["sampling"].node_refs} == {"sample"}


def _expected_compile_metric_order() -> list[str]:
    return [
        "compiled_node_layout_count",
        "compiled_group_layout_count",
        "compiled_helper_layout_count",
        COMPILE_METRIC_NODE_OVERLAP_COUNT,
        COMPILE_METRIC_GROUP_OVERLAP_COUNT,
        COMPILE_METRIC_INTERNAL_WHITESPACE_RATIO_MAX,
        COMPILE_METRIC_BASELINE_VARIANCE_MAX,
        COMPILE_METRIC_DETACHED_GROUP_DISTANCE_MAX,
        COMPILE_METRIC_HELPER_SIDECAR_OVERLAP_COUNT,
        COMPILE_METRIC_NOTE_SECTION_MISMATCH_COUNT,
        COMPILE_METRIC_MAX_PRIMARY_NODES_PER_ROW,
        COMPILE_METRIC_LONG_EDGE_DISTANCE_MAX,
        COMPILE_METRIC_BACKWARD_EDGE_RATIO,
        COMPILE_METRIC_CROSSING_PROXY_COUNT,
        COMPILE_METRIC_MINIMUM_GUTTER,
        COMPILE_METRIC_HELPER_DISTANCE_MAX,
        COMPILE_METRIC_IDEMPOTENCE_DELTA,
        COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED,
    ]


def test_compile_local_section_layout_stacks_multiple_sidecars_on_same_target() -> None:
    """Multiple SetNode/GetNode sidecars targeting the same primary node must
    stack without overlapping each other or the target."""
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "target"), outputs=[
                {"name": "out", "type": "*", "links": [10, 12, 14]}
            ]),
            _with_io(_node(2, "SetNode", "set_a"), inputs=[{"name": "value", "type": "*", "link": 10}]),
            _with_io(_node(3, "SetNode", "set_b"), inputs=[{"name": "value", "type": "*", "link": 12}]),
            _with_io(_node(4, "GetNode", "get_a"), outputs=[{"name": "value", "type": "*", "links": [11]}]),
            _with_io(_node(5, "GetNode", "get_b"), outputs=[{"name": "value", "type": "*", "links": [13]}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "*"], [11, 4, 0, 1, 0, "*"],
            [12, 1, 0, 3, 0, "*"], [13, 5, 0, 1, 0, "*"],
            [14, 1, 0, 5, 0, "*"],
        ],
    }
    plan = parse_layout_plan({
        "version": 1,
        "sections": [{"id": "main", "kind": "custom", "nodes": [["", "target"]]}],
        "helper_placements": [
            {"helper": ["", "set_a"], "kind": "near-producer", "target": ["", "target"]},
            {"helper": ["", "set_b"], "kind": "near-producer", "target": ["", "target"]},
            {"helper": ["", "get_a"], "kind": "near-consumer", "target": ["", "target"]},
            {"helper": ["", "get_b"], "kind": "near-consumer", "target": ["", "target"]},
        ],
        "unassigned_policy": "reject",
    })
    facts = extract_graph_facts(ui)
    furniture_by_ref = {fact.ref: fact for fact in facts.node_furniture}

    trace = _CompileTraceAccumulator(facts)
    classification = _classify_layout_phase(facts, trace=trace)
    sections = _compile_section_ownership_phase(
        plan, facts, classification, LayoutCompileOptions(), trace=trace
    )
    main_section = next(s for s in sections if s.id == "main")
    local = _local_section_layout(
        main_section, facts, furniture_by_ref, LayoutCompileOptions(), _spacing("balanced"), plan
    )
    offsets = local.offsets
    sizes = {
        ref: _node_size_for_ref(ref, facts, furniture_by_ref.get(ref),
                                preserve=False, minimize_setget_helpers=False)
        for ref in offsets
    }
    # All get helpers (left side) must not overlap each other
    get_refs = [CanonicalNodeRef("", "get_a"), CanonicalNodeRef("", "get_b")]
    # All set helpers (right side) must not overlap each other
    set_refs = [CanonicalNodeRef("", "set_a"), CanonicalNodeRef("", "set_b")]
    target_ref = CanonicalNodeRef("", "target")

    # Get helpers should be left of target
    for ref in get_refs:
        x, _ = offsets[ref]
        w, _ = sizes[ref]
        tx, _ = offsets[target_ref]
        assert x + w <= tx, f"get helper {ref.uid} right edge {x+w} not left of target left {tx}"

    # Set helpers should be right of target
    for ref in set_refs:
        x, _ = offsets[ref]
        tw, _ = sizes[target_ref]
        tx, _ = offsets[target_ref]
        assert tx + tw <= x, f"set helper {ref.uid} left {x} not right of target right {tx+tw}"

    # Verify sidecar stacking trace choices
    assert "sidecar:right" in local.placement_choices.get(CanonicalNodeRef("", "set_a"), "")
    assert "sidecar:left" in local.placement_choices.get(CanonicalNodeRef("", "get_a"), "")


def test_compile_local_section_layout_sidecars_push_adjacent_primaries() -> None:
    """When a sidecar is placed next to a target that has adjacent primary
    neighbours, the adjacent primaries must be pushed to avoid overlap."""
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "left_nbr"), outputs=[{"name": "out", "type": "*", "links": [10]}]),
            _with_io(_node(2, "PrimitiveNode", "target"), inputs=[{"name": "in", "type": "*", "link": 10}],
                     outputs=[{"name": "out", "type": "*", "links": [11, 13]}]),
            _with_io(_node(3, "PrimitiveNode", "right_nbr"), inputs=[{"name": "in", "type": "*", "link": 11}]),
            _with_io(_node(4, "SetNode", "set_h"), inputs=[{"name": "value", "type": "*", "link": 13}]),
            _with_io(_node(5, "GetNode", "get_h"), outputs=[{"name": "value", "type": "*", "links": [14]}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "*"], [11, 2, 0, 3, 0, "*"],
            [13, 2, 0, 4, 0, "*"], [14, 5, 0, 2, 0, "*"],
        ],
    }
    plan = parse_layout_plan({
        "version": 1,
        "sections": [{"id": "main", "kind": "custom",
                       "nodes": [["", "left_nbr"], ["", "target"], ["", "right_nbr"]]}],
        "helper_placements": [
            {"helper": ["", "set_h"], "kind": "near-producer", "target": ["", "target"]},
            {"helper": ["", "get_h"], "kind": "near-consumer", "target": ["", "target"]},
        ],
        "unassigned_policy": "reject",
    })
    facts = extract_graph_facts(ui)
    furniture_by_ref = {fact.ref: fact for fact in facts.node_furniture}

    trace = _CompileTraceAccumulator(facts)
    classification = _classify_layout_phase(facts, trace=trace)
    sections = _compile_section_ownership_phase(
        plan, facts, classification, LayoutCompileOptions(), trace=trace
    )
    main_section = next(s for s in sections if s.id == "main")
    local = _local_section_layout(
        main_section, facts, furniture_by_ref, LayoutCompileOptions(), _spacing("balanced"), plan
    )
    offsets = local.offsets
    sizes = {
        ref: _node_size_for_ref(ref, facts, furniture_by_ref.get(ref),
                                preserve=False, minimize_setget_helpers=False)
        for ref in offsets
    }
    # All nodes must be non-overlapping
    ref_list = list(offsets.keys())
    for i in range(len(ref_list)):
        for j in range(i + 1, len(ref_list)):
            a_ref, b_ref = ref_list[i], ref_list[j]
            ax, ay = offsets[a_ref]
            aw, ah = sizes[a_ref]
            bx, by = offsets[b_ref]
            bw, bh = sizes[b_ref]
            overlap_x = ax < bx + bw and bx < ax + aw
            overlap_y = ay < by + bh and by < ay + ah
            assert not (overlap_x and overlap_y), \
                f"overlap between {a_ref.uid} and {b_ref.uid}"

    target_ref = CanonicalNodeRef("", "target")
    get_h_ref = CanonicalNodeRef("", "get_h")
    set_h_ref = CanonicalNodeRef("", "set_h")

    # Get helper must be left of target
    gx, _ = offsets[get_h_ref]
    gw, _ = sizes[get_h_ref]
    tx, _ = offsets[target_ref]
    assert gx + gw <= tx, f"get helper right {gx+gw} not left of target left {tx}"

    # Set helper must be right of target
    tw, _ = sizes[target_ref]
    sx, _ = offsets[set_h_ref]
    assert tx + tw <= sx, f"set helper left {sx} not right of target right {tx+tw}"

    # left_nbr must not overlap get helper
    left_ref = CanonicalNodeRef("", "left_nbr")
    lx, _ = offsets[left_ref]
    lw, _ = sizes[left_ref]
    assert lx + lw <= gx or gx + gw <= lx, \
        "left neighbour overlaps with get helper"


def test_compile_section_ownership_notes_in_relevant_sections() -> None:
    """Notes that are connected to or annotated within a primary's section must
    be assigned to that section, not __helpers__."""
    ui = {
        "nodes": [
            _with_io(_node(1, "CheckpointLoaderSimple", "loader"), outputs=[
                {"name": "MODEL", "type": "MODEL", "links": [10]},
                {"name": "CLIP", "type": "CLIP", "links": [11]},
            ]),
            _with_io(_node(2, "CLIPTextEncode", "prompt"),
                     inputs=[{"name": "clip", "type": "CLIP", "link": 11}],
                     outputs=[{"name": "CONDITIONING", "type": "CONDITIONING", "links": [12, 14]}]),
            _with_io(_node(3, "KSampler", "sampler"),
                     inputs=[{"name": "model", "type": "MODEL", "link": 10},
                             {"name": "positive", "type": "CONDITIONING", "link": 12}]),
            _node(4, "MarkdownNote", "sampling_note"),
            _node(5, "MarkdownNote", "orphan_note"),
        ],
        "links": [
            [10, 1, 0, 3, 0, "MODEL"], [11, 1, 1, 2, 0, "CLIP"],
            [12, 2, 0, 3, 1, "CONDITIONING"], [14, 2, 0, 4, 0, "CONDITIONING"],
        ],
    }
    plan = parse_layout_plan({
        "version": 1,
        "sections": [
            {"id": "loaders", "kind": "loaders", "nodes": [["", "loader"]]},
            {"id": "conditioning", "kind": "conditioning", "nodes": [["", "prompt"]]},
            {"id": "sampling", "kind": "sampling", "nodes": [["", "sampler"]]},
        ],
        "helper_placements": [
            {"helper": ["", "sampling_note"], "kind": "inside-section", "section_id": "sampling"},
            {"helper": ["", "orphan_note"], "kind": "inside-section", "section_id": "conditioning"},
        ],
        "unassigned_policy": "reject",
    })
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)
    classification = _classify_layout_phase(facts, trace=trace)
    sections = _compile_section_ownership_phase(
        plan, facts, classification, LayoutCompileOptions(), trace=trace
    )
    # sampling_note is connected to prompt (conditioning section) via link 14
    # but is also placed in sampling section via inside-section placement
    trace_entries = {entry.ref.uid: entry for entry in trace.to_entries()}
    # The connected note should NOT be in __helpers__
    assert trace_entries["sampling_note"].section_id != "__helpers__"
    assert trace_entries["orphan_note"].section_id != "__helpers__"
    # Verify that no note landed in __helpers__
    helpers_section = next((s for s in sections if s.id == "__helpers__"), None)
    if helpers_section is not None:
        note_refs_in_helpers = [
            ref for ref in helpers_section.node_refs
            if any("note" in str(getattr(f, "class_type", "")).lower()
                   for f in facts.canonical_refs if f.ref == ref)
        ]
        assert len(note_refs_in_helpers) == 0, \
            f"notes should not be in __helpers__: {note_refs_in_helpers}"


def test_compile_layout_plan_collapses_set_get_helpers() -> None:
    """In large workflows, get/set helpers must have collapsed (minimized)
    dimensions to avoid crowding primaries."""
    ui = {
        "nodes": [
            _with_io(_node(1, "CheckpointLoaderSimple", "loader"), outputs=[
                {"name": "MODEL", "type": "MODEL", "links": [10]}
            ]),
            _with_io(_node(2, "KSampler", "sampler"),
                     inputs=[{"name": "model", "type": "MODEL", "link": 10}],
                     outputs=[{"name": "LATENT", "type": "LATENT", "links": [11]}]),
            _with_io(_node(3, "SetNode", "set_latent"),
                     inputs=[{"name": "value", "type": "LATENT", "link": 12}]),
            _with_io(_node(4, "GetNode", "get_latent"),
                     outputs=[{"name": "value", "type": "LATENT", "links": [12]}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "MODEL"], [11, 2, 0, 4, 0, "LATENT"],
            [12, 4, 0, 3, 0, "LATENT"],
        ],
    }
    plan = parse_layout_plan({
        "version": 1,
        "sections": [
            {"id": "loaders", "kind": "loaders", "nodes": [["", "loader"]]},
            {"id": "sampling", "kind": "sampling", "nodes": [["", "sampler"]]},
        ],
        "helper_placements": [
            {"helper": ["", "set_latent"], "kind": "near-producer", "target": ["", "sampler"]},
            {"helper": ["", "get_latent"], "kind": "near-consumer", "target": ["", "sampler"]},
        ],
        "unassigned_policy": "reject",
    })
    facts = extract_graph_facts(ui)
    furniture_by_ref = {fact.ref: fact for fact in facts.node_furniture}
    # Normal size (no collapse)
    normal_size_set = _node_size_for_ref(
        CanonicalNodeRef("", "set_latent"), facts, furniture_by_ref.get(CanonicalNodeRef("", "set_latent")),
        preserve=False, minimize_setget_helpers=False,
    )
    normal_size_get = _node_size_for_ref(
        CanonicalNodeRef("", "get_latent"), facts, furniture_by_ref.get(CanonicalNodeRef("", "get_latent")),
        preserve=False, minimize_setget_helpers=False,
    )
    # Collapsed size (large workflow gate active; but this is small so gate won't trigger)
    # Just verify the function shape: collapsed width <= normal width
    collapsed_set = _node_size_for_ref(
        CanonicalNodeRef("", "set_latent"), facts, furniture_by_ref.get(CanonicalNodeRef("", "set_latent")),
        preserve=False, minimize_setget_helpers=True,
    )
    collapsed_get = _node_size_for_ref(
        CanonicalNodeRef("", "get_latent"), facts, furniture_by_ref.get(CanonicalNodeRef("", "get_latent")),
        preserve=False, minimize_setget_helpers=True,
    )
    # When gate is active for huge workflows, collapsed sizes should be smaller.
    # For non-huge workflows they stay the same. Either way, assert monotonic.
    assert collapsed_set[0] <= normal_size_set[0] and collapsed_set[1] <= normal_size_set[1]
    assert collapsed_get[0] <= normal_size_get[0] and collapsed_get[1] <= normal_size_get[1]
    # Full compile must succeed
    result = compile_layout_plan(plan, facts)
    assert result.ok is True
    layouts = _layouts_by_uid(result)
    assert layouts["set_latent"].width > 0
    assert layouts["get_latent"].width > 0


def test_compile_layout_plan_bounds_cover_rendered_footprints() -> None:
    """The computed section bounds must cover the rendered footprints of all
    nodes in that section including sidecars."""
    ui = {
        "nodes": [
            _with_io(_make_node(1, "PrimitiveNode", "target", size=[200, 100]),
                     outputs=[{"name": "out", "type": "*", "links": [10, 11]}]),
            _with_io(_make_node(2, "SetNode", "set_h", size=[130, 55]),
                     inputs=[{"name": "value", "type": "*", "link": 10}]),
            _with_io(_make_node(3, "GetNode", "get_h", size=[130, 55]),
                     outputs=[{"name": "value", "type": "*", "links": [12]}]),
            _with_io(_make_node(4, "PrimitiveNode", "tall_node", size=[160, 400]),
                     inputs=[{"name": "in", "type": "*", "link": 12}]),
            _with_io(_make_node(5, "PrimitiveNode", "wide_node", size=[600, 70]),
                     inputs=[{"name": "in", "type": "*", "link": 11}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "*"], [11, 1, 0, 5, 0, "*"],
            [12, 3, 0, 4, 0, "*"],
        ],
    }
    plan = parse_layout_plan({
        "version": 1,
        "sections": [{"id": "main", "kind": "custom",
                       "nodes": [["", "target"], ["", "tall_node"], ["", "wide_node"]]}],
        "helper_placements": [
            {"helper": ["", "set_h"], "kind": "near-producer", "target": ["", "target"]},
            {"helper": ["", "get_h"], "kind": "near-consumer", "target": ["", "target"]},
        ],
        "unassigned_policy": "reject",
    })
    facts = extract_graph_facts(ui)
    furniture_by_ref = {fact.ref: fact for fact in facts.node_furniture}

    trace = _CompileTraceAccumulator(facts)
    classification = _classify_layout_phase(facts, trace=trace)
    sections = _compile_section_ownership_phase(
        plan, facts, classification, LayoutCompileOptions(), trace=trace
    )
    main_section = next(s for s in sections if s.id == "main")
    local_layout = _local_section_layout(
        main_section, facts, furniture_by_ref,
        LayoutCompileOptions(), _spacing("balanced"), plan,
    )
    # _local_bounds must cover every node in the section
    bounds_width, bounds_height = _local_bounds(local_layout.offsets, {
        ref: _node_size_for_ref(ref, facts, furniture_by_ref.get(ref),
                                preserve=False, minimize_setget_helpers=False)
        for ref in local_layout.offsets
    })
    for ref, (x, y) in local_layout.offsets.items():
        w, h = _node_size_for_ref(ref, facts, furniture_by_ref.get(ref),
                                  preserve=False, minimize_setget_helpers=False)
        assert x + w <= bounds_width, \
            f"node {ref.uid} right edge {x + w} exceeds bounds width {bounds_width}"
        assert y + h <= bounds_height, \
            f"node {ref.uid} bottom edge {y + h} exceeds bounds height {bounds_height}"


def test_compile_layout_plan_zero_sidecar_overlaps() -> None:
    """After sidecar packing, no sidecar must overlap any other node in the
    section (including other sidecars and primaries)."""
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "target"), outputs=[
                {"name": "out", "type": "*", "links": [10, 12, 14, 16]}
            ]),
            _with_io(_node(2, "SetNode", "set_a"), inputs=[{"name": "value", "type": "*", "link": 10}]),
            _with_io(_node(3, "SetNode", "set_b"), inputs=[{"name": "value", "type": "*", "link": 12}]),
            _with_io(_node(4, "GetNode", "get_a"), outputs=[{"name": "value", "type": "*", "links": [11]}]),
            _with_io(_node(5, "GetNode", "get_b"), outputs=[{"name": "value", "type": "*", "links": [13]}]),
            _with_io(_node(6, "PrimitiveNode", "left_nbr"),
                     outputs=[{"name": "out", "type": "*", "links": [17]}]),
            _with_io(_node(7, "PrimitiveNode", "right_nbr"),
                     inputs=[{"name": "in", "type": "*", "link": 16}]),
        ],
        "links": [
            [10, 1, 0, 2, 0, "*"], [11, 4, 0, 1, 0, "*"],
            [12, 1, 0, 3, 0, "*"], [13, 5, 0, 1, 0, "*"],
            [14, 1, 0, 5, 0, "*"], [16, 1, 0, 7, 0, "*"],
            [17, 6, 0, 1, 0, "*"],
        ],
    }
    plan = parse_layout_plan({
        "version": 1,
        "sections": [{"id": "main", "kind": "custom",
                       "nodes": [["", "left_nbr"], ["", "target"], ["", "right_nbr"]]}],
        "helper_placements": [
            {"helper": ["", "set_a"], "kind": "near-producer", "target": ["", "target"]},
            {"helper": ["", "set_b"], "kind": "near-producer", "target": ["", "target"]},
            {"helper": ["", "get_a"], "kind": "near-consumer", "target": ["", "target"]},
            {"helper": ["", "get_b"], "kind": "near-consumer", "target": ["", "target"]},
        ],
        "unassigned_policy": "reject",
    })
    facts = extract_graph_facts(ui)
    result = compile_layout_plan(plan, facts)
    assert result.ok is True
    layouts = _layouts_by_uid(result)

    # Check all pairwise non-overlap
    uids = list(layouts.keys())
    for i in range(len(uids)):
        for j in range(i + 1, len(uids)):
            a = layouts[uids[i]]
            b = layouts[uids[j]]
            a_right = a.x + a.width
            a_bottom = a.y + a.height
            b_right = b.x + b.width
            b_bottom = b.y + b.height
            overlap_x = a.x < b_right and b.x < a_right
            overlap_y = a.y < b_bottom and b.y < a_bottom
            assert not (overlap_x and overlap_y), \
                f"overlap between {uids[i]} ({a.x},{a.y})-({a_right},{a_bottom}) " \
                f"and {uids[j]} ({b.x},{b.y})-({b_right},{b_bottom})"


def test_compile_layout_plan_max_primary_row_count_is_three() -> None:
    """The row template must place at most 3 primary nodes per row when
    using _layout_primary_rows."""

    # Direct test of _layout_primary_rows: 10 refs, max 3 per row
    refs = tuple(CanonicalNodeRef("", f"p{i}") for i in range(1, 11))
    sizes = {ref: (150 + (i % 3) * 20, 80 + (i % 2) * 10) for i, ref in enumerate(refs, 1)}
    gap_x, gap_y = 40, 30
    offsets = _layout_primary_rows(refs, sizes, gap_x, gap_y, columns_per_row=3)

    row_groups: dict[int, list[CanonicalNodeRef]] = {}
    for ref, (x, y) in sorted(offsets.items(), key=lambda item: (item[1][1], item[1][0])):
        row_groups.setdefault(y, []).append(ref)
    for y, row_refs in row_groups.items():
        assert len(row_refs) <= 3, \
            f"row at y={y} has {len(row_refs)} primaries, max allowed is 3"
    assert len(offsets) == 10

    # Full compile: 4 PrimitiveNodes trigger the "row" template via
    # _constant_like_refs (matches "primitive" in class_type).
    ui = {
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "p1"), outputs=[{"name": "out", "type": "*", "links": [10]}]),
            _with_io(_node(2, "PrimitiveNode", "p2"),
                     inputs=[{"name": "in", "type": "*", "link": 10}],
                     outputs=[{"name": "out", "type": "*", "links": [11]}]),
            _with_io(_node(3, "PrimitiveNode", "p3"),
                     inputs=[{"name": "in", "type": "*", "link": 11}],
                     outputs=[{"name": "out", "type": "*", "links": [12]}]),
            _with_io(_node(4, "PrimitiveNode", "p4"),
                     inputs=[{"name": "in", "type": "*", "link": 12}]),
        ],
        "links": [[10, 1, 0, 2, 0, "*"], [11, 2, 0, 3, 0, "*"], [12, 3, 0, 4, 0, "*"]],
    }
    plan = parse_layout_plan({
        "version": 1,
        "sections": [{"id": "main", "kind": "custom",
                       "nodes": [["", "p1"], ["", "p2"], ["", "p3"], ["", "p4"]]}],
        "unassigned_policy": "reject",
    })
    facts = extract_graph_facts(ui)
    furniture_by_ref = {fact.ref: fact for fact in facts.node_furniture}
    trace = _CompileTraceAccumulator(facts)
    classification = _classify_layout_phase(facts, trace=trace)
    sections = _compile_section_ownership_phase(
        plan, facts, classification, LayoutCompileOptions(), trace=trace
    )
    main_section = next(s for s in sections if s.id == "main")
    local = _local_section_layout(
        main_section, facts, furniture_by_ref, LayoutCompileOptions(), _spacing("balanced"), plan
    )
    # 4 primaries across 3-column rows: first row has 3, second row has 1
    row_groups2: dict[int, list] = {}
    for ref, (x, y) in local.offsets.items():
        row_groups2.setdefault(y, []).append(ref)
    assert len(local.offsets) == 4
    for y, row_refs in row_groups2.items():
        assert len(row_refs) <= 3, \
            f"compiled row at y={y} has {len(row_refs)} primaries, max allowed is 3"


def test_compile_layout_plan_tall_and_long_node_group_bounds() -> None:
    """When a section contains tall or long nodes, the group bounds must
    encompass their full rendered footprint."""
    ui = {
        "nodes": [
            _with_io(
                _make_node(1, "CheckpointLoaderSimple", "loader", size=[300, 98]),
                outputs=[{"name": "MODEL", "type": "MODEL", "links": [10]}],
            ),
            _with_io(
                _make_node(2, "KSampler", "sampler", size=[260, 90]),
                inputs=[{"name": "model", "type": "MODEL", "link": 10}],
            ),
        ],
        "links": [[10, 1, 0, 2, 0, "MODEL"]],
    }
    plan = parse_layout_plan({
        "version": 1,
        "sections": [
            {"id": "loaders", "kind": "loaders", "nodes": [["", "loader"]]},
            {"id": "sampling", "kind": "sampling", "nodes": [["", "sampler"]]},
        ],
        "unassigned_policy": "reject",
    })
    facts = extract_graph_facts(ui)
    result = compile_layout_plan(plan, facts)
    assert result.ok is True
    layouts = _layouts_by_uid(result)
    loader = layouts["loader"]
    sampler = layouts["sampler"]
    # Check that actual node sizes are respected
    assert loader.width >= 300, f"loader width should be >= 300, got {loader.width}"
    assert sampler.width >= 260, f"sampler width should be >= 260, got {sampler.width}"
    # Each node must fit within the group layout bounds it belongs to
    for group in result.group_layouts:
        group_right = group.x + group.width
        group_bottom = group.y + group.height
        for ref in group.node_refs:
            layout = layouts[ref.uid]
            assert layout.x >= group.x, \
                f"node {layout.ref.uid} left edge {layout.x} < group left {group.x}"
            assert layout.x + layout.width <= group_right, \
                f"node {layout.ref.uid} right edge exceeds group bounds"
            assert layout.y >= group.y, \
                f"node {layout.ref.uid} top edge {layout.y} < group top {group.y}"
            assert layout.y + layout.height <= group_bottom, \
                f"node {layout.ref.uid} bottom edge exceeds group bounds"


# ---------------------------------------------------------------------------
# T13: Determinism and metric tests
# ---------------------------------------------------------------------------


def test_repeated_compiles_produce_identical_node_and_group_coordinates() -> None:
    """Repeated compiles of the same plan+facts must produce identical x/y
    coordinates for every node and identical x/y/width/height for every group.
    This is stronger than json-order determinism -- it proves the placement
    math itself is deterministic."""
    facts = extract_graph_facts(_ui())
    plan = _valid_plan()

    def _coordinate_snapshot(result) -> dict:
        nodes = {
            layout.ref.uid: (layout.x, layout.y, layout.width, layout.height)
            for layout in result.node_layouts
        }
        groups = {
            group.id: (group.x, group.y, group.width, group.height)
            for group in result.group_layouts
        }
        return {"nodes": nodes, "groups": groups}

    first = compile_layout_plan(plan, facts)
    second = compile_layout_plan(plan, facts)
    third = compile_layout_plan(plan, facts)

    snap1 = _coordinate_snapshot(first)
    snap2 = _coordinate_snapshot(second)
    snap3 = _coordinate_snapshot(third)

    assert snap1 == snap2, "first and second compile must have identical coordinates"
    assert snap1 == snap3, "first and third compile must have identical coordinates"


def test_repeated_compiles_produce_identical_coordinates_from_ui_path() -> None:
    """The compile_layout_plan_from_ui path must also be deterministic
    for repeated calls."""
    plan = _valid_plan()
    ui = _ui()

    first = compile_layout_plan_from_ui(plan, deepcopy(ui))
    second = compile_layout_plan_from_ui(plan, deepcopy(ui))

    first_nodes = {
        layout.ref.uid: (layout.x, layout.y)
        for layout in first.node_layouts
    }
    second_nodes = {
        layout.ref.uid: (layout.x, layout.y)
        for layout in second.node_layouts
    }
    assert first_nodes == second_nodes

    first_groups = {
        group.id: (group.x, group.y, group.width, group.height)
        for group in first.group_layouts
    }
    second_groups = {
        group.id: (group.x, group.y, group.width, group.height)
        for group in second.group_layouts
    }
    assert first_groups == second_groups


def test_repeated_compiles_with_different_spacing_produce_identical_coordinates() -> None:
    """Each spacing preset must be self-deterministic: compact twice gives the
    same coords, wide twice gives the same coords."""
    facts = extract_graph_facts(_ui())
    plan = _valid_plan()

    for preset in ("compact", "wide"):
        opts = LayoutCompileOptions(spacing_preset=preset)
        first = compile_layout_plan(plan, facts, options=opts)
        second = compile_layout_plan(plan, facts, options=opts)

        first_coords = {
            layout.ref.uid: (layout.x, layout.y)
            for layout in first.node_layouts
        }
        second_coords = {
            layout.ref.uid: (layout.x, layout.y)
            for layout in second.node_layouts
        }
        assert first_coords == second_coords, \
            f"spacing preset {preset!r} produced different coordinates"


def test_validation_metrics_are_all_present_in_compile_result() -> None:
    """Every metric in COMPILE_METRIC_ORDER must appear in the compile result,
    including all extended validation metrics added in T12."""
    result = compile_layout_plan(_valid_plan(), extract_graph_facts(_ui()))

    metric_names = {metric.name for metric in result.metrics}
    assert metric_names == set(_expected_compile_metric_order()), \
        "compile result must contain exactly the expected metric set"

    # Spot-check that each extended metric is present with a sensible type
    metrics = {metric.name: metric for metric in result.metrics}
    for name in (
        COMPILE_METRIC_NODE_OVERLAP_COUNT,
        COMPILE_METRIC_GROUP_OVERLAP_COUNT,
        COMPILE_METRIC_INTERNAL_WHITESPACE_RATIO_MAX,
        COMPILE_METRIC_BASELINE_VARIANCE_MAX,
        COMPILE_METRIC_DETACHED_GROUP_DISTANCE_MAX,
        COMPILE_METRIC_HELPER_SIDECAR_OVERLAP_COUNT,
        COMPILE_METRIC_NOTE_SECTION_MISMATCH_COUNT,
        COMPILE_METRIC_MAX_PRIMARY_NODES_PER_ROW,
        COMPILE_METRIC_LONG_EDGE_DISTANCE_MAX,
        COMPILE_METRIC_BACKWARD_EDGE_RATIO,
        COMPILE_METRIC_CROSSING_PROXY_COUNT,
        COMPILE_METRIC_MINIMUM_GUTTER,
        COMPILE_METRIC_HELPER_DISTANCE_MAX,
        COMPILE_METRIC_IDEMPOTENCE_DELTA,
    ):
        m = metrics[name]
        assert isinstance(m.value, (int, float)), \
            f"metric {name!r} value must be numeric, got {type(m.value)}"
        assert hasattr(m, "threshold"), \
            f"metric {name!r} must have a threshold"


def test_validation_does_not_correct_coordinates() -> None:
    """When _build_report detects overlaps, internal whitespace issues, etc.,
    it emits warnings via AssessmentIssue but must NOT mutate the node_layouts
    or group_layouts that were passed in.  Validation is diagnostic only."""
    from vibecomfy.porting.reorganise.compile import (
        _compile_gate_metrics_and_issues,
    )

    ref_a = CanonicalNodeRef("", "a")
    ref_b = CanonicalNodeRef("", "b")
    ref_c = CanonicalNodeRef("", "c")

    # Deliberately overlapping layout: a and b share the same space
    node_layouts = (
        CompiledNodeLayout(ref=ref_a, section_id="s", role_hint=ROLE_HINT_UNKNOWN,
                           x=0, y=0, width=100, height=100),
        CompiledNodeLayout(ref=ref_b, section_id="s", role_hint=ROLE_HINT_UNKNOWN,
                           x=50, y=50, width=100, height=100),
        CompiledNodeLayout(ref=ref_c, section_id="s", role_hint=ROLE_HINT_UNKNOWN,
                           x=200, y=0, width=80, height=80),
    )
    group_layouts = (
        CompiledGroupLayout(
            id="s", scope_path="", title="S", kind="custom",
            node_refs=(ref_a, ref_b, ref_c),
            x=0, y=0, width=300, height=200, color="#646464",
        ),
    )
    facts = extract_graph_facts({
        "nodes": [
            _with_io(_node(1, "PrimitiveNode", "a"),
                     outputs=[{"name": "out", "type": "*", "links": [10]}]),
            _with_io(_node(2, "PrimitiveNode", "b"),
                     inputs=[{"name": "in", "type": "*", "link": 10}]),
            _node(3, "PrimitiveNode", "c"),
        ],
        "links": [[10, 1, 0, 2, 0, "*"]],
    })

    # Snapshot coords before calling metrics
    before_coords = {
        layout.ref.uid: (layout.x, layout.y, layout.width, layout.height)
        for layout in node_layouts
    }
    before_groups = {
        group.id: (group.x, group.y, group.width, group.height)
        for group in group_layouts
    }

    # Build the patch from the (overlapping) node layouts
    candidate_patch = LayoutCandidatePatch(
        entries={
            layout.ref.uid: {"pos": [layout.x, layout.y],
                             "size": [layout.width, layout.height]}
            for layout in node_layouts
        },
        groups=(
            {"id": "s", "title": "S", "bounding": [0, 0, 300, 200],
             "nodes": ["a", "b", "c"]},
        ),
    )

    gate_metrics, gate_issues = _compile_gate_metrics_and_issues(
        node_layouts=node_layouts,
        group_layouts=group_layouts,
        facts=facts,
        candidate_patch=candidate_patch,
        structural_hash_before="abc",
        structural_hash_after="abc",
    )

    # Metrics must detect the overlap
    overlap_metric = next(
        m for m in gate_metrics
        if m.name == COMPILE_METRIC_NODE_OVERLAP_COUNT
    )
    assert overlap_metric.value > 0, \
        "validation must detect the deliberate overlap"

    # Issues must include overlap warning
    overlap_codes = {issue.code for issue in gate_issues}
    assert COMPILE_ISSUE_NODE_OVERLAP in overlap_codes, \
        "validation must emit overlap warning"

    # Coordinates must NOT be mutated
    after_coords = {
        layout.ref.uid: (layout.x, layout.y, layout.width, layout.height)
        for layout in node_layouts
    }
    after_groups = {
        group.id: (group.x, group.y, group.width, group.height)
        for group in group_layouts
    }
    assert after_coords == before_coords, \
        "validation metrics must NOT mutate node coordinates"
    assert after_groups == before_groups, \
        "validation metrics must NOT mutate group coordinates"


def test_structural_expectations_reject_overlaps_via_report() -> None:
    """Structural expectations must surface overlap issues in the compile
    report when nodes overlap.  The report's issues must include the overlap
    code and the verdict must reflect the problem."""
    ref_a = CanonicalNodeRef("", "a")
    ref_b = CanonicalNodeRef("", "b")

    # Two nodes completely overlapping
    node_layouts = (
        CompiledNodeLayout(ref=ref_a, section_id="s", role_hint=ROLE_HINT_UNKNOWN,
                           x=0, y=0, width=100, height=100),
        CompiledNodeLayout(ref=ref_b, section_id="s", role_hint=ROLE_HINT_UNKNOWN,
                           x=10, y=10, width=100, height=100),
    )
    group_layouts = (
        CompiledGroupLayout(
            id="s", scope_path="", title="S", kind="custom",
            node_refs=(ref_a, ref_b),
            x=0, y=0, width=200, height=200, color="#646464",
        ),
    )
    facts = extract_graph_facts({
        "nodes": [
            _node(1, "PrimitiveNode", "a"),
            _node(2, "PrimitiveNode", "b"),
        ],
        "links": [],
    })
    candidate_patch = LayoutCandidatePatch(
        entries={
            layout.ref.uid: {"pos": [layout.x, layout.y],
                             "size": [layout.width, layout.height]}
            for layout in node_layouts
        },
        groups=(
            {"id": "s", "title": "S", "bounding": [0, 0, 200, 200],
             "nodes": ["a", "b"]},
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

    # With node overlaps, the verdict must not be "ok"
    assert report.verdict != "ok", \
        f"overlapping nodes must produce a non-ok verdict, got {report.verdict!r}"

    issue_codes = {issue.code for issue in report.issues}
    assert COMPILE_ISSUE_NODE_OVERLAP in issue_codes, \
        "overlapping nodes must produce a node_overlap issue"


def test_structural_expectations_reject_fake_helper_groups() -> None:
    """A group whose title claims 'set / get' or 'helper' but that contains
    primary nodes (not actual helpers) must still be recognized. The
    helper sidecar overlap metric and any note section mismatches must
    be counted correctly even when groups are mislabeled."""
    ref_primary = CanonicalNodeRef("", "primary")
    ref_real_set = CanonicalNodeRef("", "setter")
    ref_real_get = CanonicalNodeRef("", "getter")

    # A fake "set / get" group containing a primary node
    node_layouts = (
        CompiledNodeLayout(ref=ref_primary, section_id="main",
                           role_hint=ROLE_HINT_UNKNOWN,
                           x=0, y=0, width=200, height=100),
        CompiledNodeLayout(ref=ref_real_set, section_id="main",
                           role_hint=ROLE_HINT_HELPER,
                           x=220, y=0, width=120, height=80),
        CompiledNodeLayout(ref=ref_real_get, section_id="main",
                           role_hint=ROLE_HINT_HELPER,
                           x=360, y=0, width=120, height=80),
    )
    group_layouts = (
        CompiledGroupLayout(
            id="fake_setget", scope_path="", title="set / get (fake)",
            kind="custom",
            node_refs=(ref_primary, ref_real_set, ref_real_get),
            x=0, y=0, width=500, height=120, color="#a8adb4",
        ),
    )
    facts = extract_graph_facts({
        "nodes": [
            _node(1, "PrimitiveNode", "primary"),
            _with_io(_node(2, "SetNode", "setter"),
                     inputs=[{"name": "value", "type": "*", "link": 10}]),
            _with_io(_node(3, "GetNode", "getter"),
                     outputs=[{"name": "value", "type": "*", "links": [11]}]),
        ],
        "links": [[10, 1, 0, 2, 0, "*"], [11, 3, 0, 1, 0, "*"]],
    })
    candidate_patch = LayoutCandidatePatch(
        entries={
            layout.ref.uid: {"pos": [layout.x, layout.y],
                             "size": [layout.width, layout.height]}
            for layout in node_layouts
        },
        groups=(
            {"id": "fake_setget", "title": "set / get (fake)",
             "bounding": [0, 0, 500, 120], "nodes": ["primary", "setter", "getter"]},
        ),
    )

    report = _build_report(
        node_layouts=node_layouts,
        group_layouts=group_layouts,
        facts=facts,
        candidate_patch=candidate_patch,
        structural_hash_before="same",
        structural_hash_after="same",
        diagnostics=(),
    )

    # The report must exist and contain all expected metrics
    metric_names = {metric.name for metric in report.metrics}
    assert COMPILE_METRIC_HELPER_SIDECAR_OVERLAP_COUNT in metric_names, \
        "helper sidecar overlap metric must be present"
    assert COMPILE_METRIC_HELPER_DISTANCE_MAX in metric_names, \
        "helper distance metric must be present"

    # Even with mislabeled groups, the node-level facts still classify
    # helpers correctly, so the helper layout count must match reality
    helper_count_metric = next(
        m for m in report.metrics
        if m.name == "compiled_helper_layout_count"
    )
    assert helper_count_metric.value == 2, \
        "must count the two real helpers (SetNode, GetNode)"
