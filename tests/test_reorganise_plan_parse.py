from __future__ import annotations

import pytest

from vibecomfy.porting.reorganise.parse import (
    LAYOUT_PLAN_SCHEMA_V1,
    LayoutPlanParseError,
    parse_layout_plan,
)
from vibecomfy.porting.reorganise.plan_types import (
    UNASSIGNED_CLASSIFY_DETERMINISTICALLY,
    UNASSIGNED_REJECT,
)


def _valid_plan() -> dict[str, object]:
    return {
        "version": 1,
        "sections": [
            {
                "id": "sampling",
                "kind": "sampling",
                "nodes": [["", "ksampler"]],
                "title": "Sampling",
                "role_hint": "sampler",
            }
        ],
        "shared_nodes": [
            {
                "node": ["", "checkpoint"],
                "home": "loaders",
                "label": "Checkpoint",
            }
        ],
        "helper_placements": [
            {
                "helper": ["", "reroute-1"],
                "kind": "edge-path",
                "from": ["", "ksampler"],
                "to": ["", "vae-decode"],
                "reason": "Keep the latent edge readable.",
            }
        ],
        "sampler_relations": [
            {
                "kind": "sampler_precedes",
                "samplers": [["", "ksampler"], ["", "refiner"]],
                "source": ["", "ksampler"],
                "target": ["", "refiner"],
            }
        ],
        "notes": "layout-only",
    }


def _diagnostic_codes(exc: LayoutPlanParseError) -> list[str]:
    return [diagnostic.code for diagnostic in exc.diagnostics]


def test_parse_layout_plan_accepts_valid_minimal_plan_and_defaults_policy() -> None:
    plan = parse_layout_plan({"version": 1, "sections": []})

    assert plan.version == 1
    assert plan.sections == ()
    assert plan.shared_nodes == ()
    assert plan.helper_placements == ()
    assert plan.sampler_relations == ()
    assert plan.unassigned_policy == UNASSIGNED_CLASSIFY_DETERMINISTICALLY
    assert plan.to_json()["unassigned_policy"] == UNASSIGNED_CLASSIFY_DETERMINISTICALLY


def test_parse_layout_plan_accepts_full_shape_and_explicit_policy() -> None:
    payload = _valid_plan()
    payload["unassigned_policy"] = UNASSIGNED_REJECT

    plan = parse_layout_plan(payload)

    assert plan.unassigned_policy == UNASSIGNED_REJECT
    assert plan.sections[0].nodes[0].to_json() == ["", "ksampler"]
    assert plan.shared_nodes[0].node.to_json() == ["", "checkpoint"]
    assert plan.helper_placements[0].source is not None
    assert plan.helper_placements[0].source.to_json() == ["", "ksampler"]
    assert plan.sampler_relations[0].samplers[1].to_json() == ["", "refiner"]


def test_parse_layout_plan_extracts_json_fence() -> None:
    plan = parse_layout_plan(
        """
        ```json
        {"version": 1, "sections": []}
        ```
        """
    )

    assert plan.version == 1
    assert plan.sections == ()


def test_parse_layout_plan_exposes_in_code_schema_dictionary() -> None:
    assert LAYOUT_PLAN_SCHEMA_V1["properties"]["version"] == {"const": 1}
    assert LAYOUT_PLAN_SCHEMA_V1["properties"]["sections"]["items"]["additionalProperties"] is False
    assert LAYOUT_PLAN_SCHEMA_V1["$defs"]["canonicalNodeRef"]["minItems"] == 2


def test_parse_layout_plan_rejects_unknown_top_level_and_nested_keys_in_order() -> None:
    payload = _valid_plan()
    payload["surprise"] = True
    sections = payload["sections"]
    assert isinstance(sections, list)
    sections[0]["extra"] = "nope"

    with pytest.raises(LayoutPlanParseError) as caught:
        parse_layout_plan(payload)

    assert _diagnostic_codes(caught.value)[:2] == ["unknown_field", "unknown_field"]
    assert [diagnostic.path for diagnostic in caught.value.diagnostics[:2]] == [
        ("surprise",),
        ("sections", 0, "extra"),
    ]


def test_parse_layout_plan_rejects_backend_owned_fields() -> None:
    payload = _valid_plan()
    payload["flows"] = []
    shared_nodes = payload["shared_nodes"]
    assert isinstance(shared_nodes, list)
    shared_nodes[0]["consumers"] = [["", "ksampler"]]

    with pytest.raises(LayoutPlanParseError) as caught:
        parse_layout_plan(payload)

    assert _diagnostic_codes(caught.value)[:2] == ["backend_owned_field", "backend_owned_field"]
    assert [diagnostic.path for diagnostic in caught.value.diagnostics[:2]] == [
        ("flows",),
        ("shared_nodes", 0, "consumers"),
    ]


def test_parse_layout_plan_rejects_unknown_section_kind() -> None:
    payload = _valid_plan()
    sections = payload["sections"]
    assert isinstance(sections, list)
    sections[0]["kind"] = "magic"

    with pytest.raises(LayoutPlanParseError) as caught:
        parse_layout_plan(payload)

    assert _diagnostic_codes(caught.value) == ["unknown_section_kind"]
    assert caught.value.diagnostics[0].path == ("sections", 0, "kind")


@pytest.mark.parametrize("bad_ref", ["ksampler", 7])
def test_parse_layout_plan_rejects_bare_refs(bad_ref: object) -> None:
    payload = _valid_plan()
    sections = payload["sections"]
    assert isinstance(sections, list)
    sections[0]["nodes"] = [bad_ref]

    with pytest.raises(LayoutPlanParseError) as caught:
        parse_layout_plan(payload)

    assert _diagnostic_codes(caught.value) == ["bare_ref_not_allowed"]
    assert caught.value.diagnostics[0].path == ("sections", 0, "nodes", 0)


@pytest.mark.parametrize(
    ("placement", "codes"),
    [
        (
            {
                "helper": ["", "reroute-1"],
                "kind": "near-producer",
            },
            ["missing_helper_target"],
        ),
        (
            {
                "helper": ["", "reroute-1"],
                "kind": "edge-path",
                "from": ["", "ksampler"],
            },
            ["missing_helper_edge_endpoint"],
        ),
        (
            {
                "helper": ["", "note-1"],
                "kind": "inside-section",
            },
            ["missing_helper_section"],
        ),
        (
            {
                "helper": ["", "note-1"],
                "kind": "floating",
            },
            ["unknown_helper_placement_kind"],
        ),
    ],
)
def test_parse_layout_plan_rejects_malformed_helper_placements(
    placement: dict[str, object],
    codes: list[str],
) -> None:
    payload = _valid_plan()
    payload["helper_placements"] = [placement]

    with pytest.raises(LayoutPlanParseError) as caught:
        parse_layout_plan(payload)

    assert _diagnostic_codes(caught.value) == codes


def test_parse_layout_plan_rejects_unknown_unassigned_policy() -> None:
    payload = _valid_plan()
    payload["unassigned_policy"] = "invent"

    with pytest.raises(LayoutPlanParseError) as caught:
        parse_layout_plan(payload)

    assert _diagnostic_codes(caught.value) == ["unknown_unassigned_policy"]
    assert caught.value.diagnostics[0].path == ("unassigned_policy",)
