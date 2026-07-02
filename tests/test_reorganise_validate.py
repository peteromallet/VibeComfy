from __future__ import annotations

from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts
from vibecomfy.porting.reorganise.parse import parse_layout_plan
from vibecomfy.porting.reorganise.plan_types import CanonicalNodeRef, LayoutPlanV1, LayoutSection
from vibecomfy.porting.reorganise.validate import validate_layout_plan, validate_layout_plan_from_ui


def _node(node_id: int, class_type: str, uid: str) -> dict:
    return {
        "id": node_id,
        "type": class_type,
        "class_type": class_type,
        "properties": {"vibecomfy_uid": uid},
    }


def _ui() -> dict:
    return {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "CLIPTextEncode", "positive"),
            _node(3, "KSampler", "sample"),
            _node(4, "VAEDecode", "decode"),
            _node(5, "SaveImage", "save"),
            _node(6, "Reroute", "reroute"),
            _node(7, "MarkdownNote", "note"),
        ],
        "links": [],
    }


def _linked_sampler_ui() -> dict:
    return {
        "nodes": [
            _node(1, "KSampler", "sample-a"),
            _node(2, "KSampler", "sample-b"),
            _node(3, "SaveImage", "save"),
        ],
        "links": [
            [10, 1, 0, 2, 0, "LATENT"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
    }


def _subgraph_ui() -> dict:
    return {
        "nodes": [_node(1, "SubgraphContainer", "container")],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "name": "Inner",
                    "nodes": [_node(10, "KSampler", "inner-sample")],
                    "links": [],
                }
            ]
        },
    }


def _codes(report) -> list[str]:
    return [diagnostic.code for diagnostic in report.diagnostics]


def test_validate_layout_plan_accepts_exact_primary_ownership_and_helper_channel() -> None:
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "loaders",
                    "kind": "loaders",
                    "nodes": [["", "checkpoint"]],
                },
                {
                    "id": "conditioning",
                    "kind": "conditioning",
                    "nodes": [["", "positive"]],
                },
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample"]],
                },
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
                },
                {
                    "helper": ["", "note"],
                    "kind": "near-consumer",
                    "target": ["", "save"],
                },
            ],
            "unassigned_policy": "reject",
        }
    )

    report = validate_layout_plan_from_ui(plan, _ui())

    assert report.ok is True
    assert report.diagnostics == ()


def test_validate_layout_plan_rejects_duplicate_primary_ownership() -> None:
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample"], ["", "positive"], ["", "decode"], ["", "save"]],
                },
                {
                    "id": "output",
                    "kind": "output",
                    "nodes": [["", "save"], ["", "checkpoint"]],
                },
            ],
            "unassigned_policy": "reject",
        }
    )

    report = validate_layout_plan(plan, extract_graph_facts(_ui()))

    assert report.ok is False
    assert _codes(report) == ["duplicate_primary_ownership"]
    assert report.diagnostics[0].detail["ref"] == ["", "save"]
    assert [owner["section_id"] for owner in report.diagnostics[0].detail["owners"]] == [
        "sampling",
        "output",
    ]


def test_validate_layout_plan_rejects_missing_ownership_when_policy_is_reject() -> None:
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample"]],
                }
            ],
            "unassigned_policy": "reject",
        }
    )

    report = validate_layout_plan(plan, extract_graph_facts(_ui()))

    assert report.ok is False
    assert _codes(report) == [
        "missing_primary_ownership",
        "missing_primary_ownership",
        "missing_primary_ownership",
        "missing_primary_ownership",
    ]
    assert [diagnostic.detail["ref"][1] for diagnostic in report.diagnostics] == [
        "checkpoint",
        "positive",
        "decode",
        "save",
    ]


def test_validate_layout_plan_allows_missing_ownership_with_deterministic_classification() -> None:
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample"]],
                }
            ],
        }
    )

    report = validate_layout_plan(plan, extract_graph_facts(_ui()))

    assert report.ok is True
    assert _codes(report) == [
        "unassigned_classified_deterministically",
        "unassigned_classified_deterministically",
        "unassigned_classified_deterministically",
        "unassigned_classified_deterministically",
    ]
    assert {diagnostic.severity for diagnostic in report.diagnostics} == {"info"}


def test_validate_layout_plan_rejects_unknown_refs_and_section_ids() -> None:
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample"], ["", "ghost"]],
                    "parent_id": "missing-parent",
                }
            ],
            "shared_nodes": [{"node": ["", "checkpoint"], "home": "loaders"}],
            "helper_placements": [
                {
                    "helper": ["", "missing-helper"],
                    "kind": "inside-section",
                    "section_id": "helpers",
                }
            ],
            "sampler_relations": [
                {
                    "kind": "sampler_precedes",
                    "samplers": [["", "sample"], ["", "missing-sampler"]],
                }
            ],
            "unassigned_policy": "reject",
        }
    )

    report = validate_layout_plan(plan, extract_graph_facts(_ui()))

    assert report.ok is False
    assert _codes(report)[:6] == [
        "unknown_section_id",
        "unknown_ref",
        "unknown_section_id",
        "unknown_ref",
        "unknown_section_id",
        "unknown_ref",
    ]
    assert report.diagnostics[0].path == ("sections", 0, "parent_id")
    assert report.diagnostics[1].path == ("sections", 0, "nodes", 1)
    assert report.diagnostics[2].path == ("shared_nodes", 0, "home")
    assert report.diagnostics[3].path == ("helper_placements", 0, "helper")
    assert report.diagnostics[4].path == ("helper_placements", 0, "section_id")
    assert report.diagnostics[5].path == ("sampler_relations", 0, "samplers", 1)


def test_validate_layout_plan_rejects_helper_nodes_in_primary_ownership_channels() -> None:
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample"], ["", "reroute"]],
                },
                {
                    "id": "output",
                    "kind": "output",
                    "nodes": [["", "checkpoint"], ["", "positive"], ["", "decode"], ["", "save"]],
                },
            ],
            "shared_nodes": [{"node": ["", "note"], "home": "output"}],
            "unassigned_policy": "reject",
        }
    )

    report = validate_layout_plan(plan, extract_graph_facts(_ui()))

    assert report.ok is False
    assert _codes(report) == ["helper_primary_ownership", "helper_primary_ownership"]
    assert report.diagnostics[0].path == ("sections", 0, "nodes", 1)
    assert report.diagnostics[1].path == ("shared_nodes", 0, "node")


def test_validate_layout_plan_catches_parser_bypass_bare_refs_and_shared_consumers() -> None:
    plan = LayoutPlanV1(
        sections=(
            LayoutSection(
                id="sampling",
                kind="sampling",
                nodes=("sample",),  # type: ignore[arg-type]
            ),
        ),
        shared_nodes=(
            {
                "node": ["", "checkpoint"],
                "home": "sampling",
                "consumers": [["", "sample"]],
            },  # type: ignore[arg-type]
        ),
        unassigned_policy="reject",
    )

    report = validate_layout_plan(plan, extract_graph_facts(_ui()))

    assert report.ok is False
    assert _codes(report)[:3] == [
        "bare_ref_not_allowed",
        "backend_owned_field",
        "bare_ref_not_allowed",
    ]
    assert report.diagnostics[0].path == ("sections", 0, "nodes", 0)
    assert report.diagnostics[1].path == ("shared_nodes", 0, "consumers")
    assert report.diagnostics[2].path == ("shared_nodes", 0, "node")


def test_validate_layout_plan_rejects_forbidden_coordinate_and_topology_payloads() -> None:
    plan = LayoutPlanV1(
        sections=(
            LayoutSection(
                id="all",
                kind="custom",
                nodes=(
                    CanonicalNodeRef("", "checkpoint"),
                    CanonicalNodeRef("", "positive"),
                    CanonicalNodeRef("", "sample"),
                    CanonicalNodeRef("", "decode"),
                    CanonicalNodeRef("", "save"),
                ),
            ),
        ),
        helper_placements=(
            {
                "helper": CanonicalNodeRef("", "reroute"),
                "kind": "inside-section",
                "section_id": "all",
                "pos": [100, 200],
                "links": [],
            },
        ),  # type: ignore[arg-type]
        unassigned_policy="reject",
    )

    report = validate_layout_plan(plan, extract_graph_facts(_ui()))

    assert report.ok is False
    assert _codes(report) == ["forbidden_layout_payload", "forbidden_layout_payload"]
    assert [diagnostic.path[-1] for diagnostic in report.diagnostics] == ["links", "pos"]


def test_validate_layout_plan_enforces_helper_placement_shapes_and_targets() -> None:
    shape_plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "all",
                    "kind": "custom",
                    "nodes": [
                        ["", "checkpoint"],
                        ["", "positive"],
                        ["", "sample"],
                        ["", "decode"],
                        ["", "save"],
                    ],
                }
            ],
            "helper_placements": [
                {
                    "helper": ["", "reroute"],
                    "kind": "near-producer",
                    "target": ["", "sample"],
                    "section_id": "all",
                }
            ],
            "unassigned_policy": "reject",
        }
    )
    target_plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "all",
                    "kind": "custom",
                    "nodes": [
                        ["", "checkpoint"],
                        ["", "positive"],
                        ["", "sample"],
                        ["", "decode"],
                        ["", "save"],
                    ],
                }
            ],
            "helper_placements": [
                {
                    "helper": ["", "sample"],
                    "kind": "near-consumer",
                    "target": ["", "reroute"],
                }
            ],
            "unassigned_policy": "reject",
        }
    )

    shape_report = validate_layout_plan(shape_plan, extract_graph_facts(_ui()))
    target_report = validate_layout_plan(target_plan, extract_graph_facts(_ui()))

    assert shape_report.ok is False
    assert _codes(shape_report) == ["invalid_helper_placement_shape"]
    assert shape_report.diagnostics[0].detail["forbidden"] == ["section_id"]
    assert target_report.ok is False
    assert _codes(target_report) == [
        "invalid_helper_placement_helper",
        "invalid_helper_target",
    ]


def test_validate_layout_plan_rejects_cross_scope_primary_ownership_and_requires_container_parent() -> None:
    facts = extract_graph_facts(_subgraph_ui())
    inner_ref = next(fact.ref for fact in facts.canonical_refs if fact.ref.scope_path)
    cross_scope_plan = LayoutPlanV1(
        sections=(
            LayoutSection(
                id="mixed",
                kind="custom",
                nodes=(CanonicalNodeRef("", "container"), inner_ref),
            ),
        ),
        unassigned_policy="reject",
    )
    orphan_inner_plan = LayoutPlanV1(
        sections=(
            LayoutSection(
                id="inner",
                kind="sampling",
                nodes=(inner_ref,),
            ),
            LayoutSection(
                id="root",
                kind="custom",
                nodes=(CanonicalNodeRef("", "container"),),
            ),
        ),
        unassigned_policy="reject",
    )
    container_parent_plan = LayoutPlanV1(
        sections=(
            LayoutSection(
                id="root-container",
                kind="container",
                nodes=(CanonicalNodeRef("", "container"),),
            ),
            LayoutSection(
                id="inner",
                kind="sampling",
                nodes=(inner_ref,),
                parent_id="root-container",
            ),
        ),
        unassigned_policy="reject",
    )

    cross_scope_report = validate_layout_plan(cross_scope_plan, facts)
    orphan_inner_report = validate_layout_plan(orphan_inner_plan, facts)
    container_parent_report = validate_layout_plan(container_parent_plan, facts)

    assert cross_scope_report.ok is False
    assert _codes(cross_scope_report) == ["cross_scope_primary_ownership"]
    assert orphan_inner_report.ok is False
    assert _codes(orphan_inner_report) == ["subgraph_boundary_violation"]
    assert container_parent_report.ok is True
    assert container_parent_report.diagnostics == ()


def test_validate_layout_plan_rejects_sampler_claims_contradicted_by_topology() -> None:
    plan = parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "sampling",
                    "kind": "sampling",
                    "nodes": [["", "sample-a"], ["", "sample-b"], ["", "save"]],
                }
            ],
            "sampler_relations": [
                {
                    "kind": "sampler_precedes",
                    "samplers": [["", "sample-a"], ["", "sample-b"]],
                    "source": ["", "sample-b"],
                    "target": ["", "sample-a"],
                }
            ],
            "unassigned_policy": "reject",
        }
    )

    report = validate_layout_plan(plan, extract_graph_facts(_linked_sampler_ui()))

    assert report.ok is False
    assert _codes(report) == ["sampler_relation_contradiction"]
    assert report.diagnostics[0].detail["claimed_source"] == ["", "sample-b"]
    assert report.diagnostics[0].detail["proven"][0]["source"] == ["", "sample-a"]
