from __future__ import annotations

from vibecomfy.porting.reorganise import CanonicalNodeRef, LayoutCompileOptions, compile_layout_plan
from vibecomfy.porting.reorganise.classify import classify_layout_facts
from vibecomfy.porting.reorganise.compile import _score_existing_group
from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts
from vibecomfy.porting.reorganise.parse import parse_layout_plan


def _node(node_id: int, class_type: str, uid: str, pos: tuple[int, int]) -> dict:
    return {
        "id": node_id,
        "type": class_type,
        "class_type": class_type,
        "pos": list(pos),
        "size": [160, 80],
        "properties": {"vibecomfy_uid": uid},
    }


def _prompt_pair_ui(
    *,
    group_bounding: list[int],
    group_title: str = "Prompts",
    group_color: str | None = None,
) -> dict:
    group = {"title": group_title, "bounding": group_bounding, "nodes": [2, 3]}
    if group_color is not None:
        group["color"] = group_color
    return {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint", (20, 40)),
            _node(2, "CLIPTextEncode", "positive", (300, 60)),
            _node(3, "CLIPTextEncode", "negative", (300, 180)),
            _node(4, "KSampler", "sample", (620, 120)),
            _node(5, "SaveImage", "save", (900, 120)),
        ],
        "links": [
            [10, 1, 0, 2, 0, "CLIP"],
            [11, 1, 0, 3, 0, "CLIP"],
            [12, 2, 0, 4, 1, "CONDITIONING"],
            [13, 3, 0, 4, 2, "CONDITIONING"],
            [14, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [group],
    }


def _preserve_existing_plan():
    return parse_layout_plan(
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


def _explicit_prompt_pair_plan():
    return parse_layout_plan(
        {
            "version": 1,
            "sections": [
                {
                    "id": "conditioning",
                    "kind": "conditioning",
                    "title": "Semantic Prompts",
                    "nodes": [["", "positive"], ["", "negative"]],
                }
            ],
            "unassigned_policy": "classify_deterministically",
        }
    )


def _node_sections(result) -> dict[str, str]:
    return {layout.ref.uid: layout.section_id for layout in result.node_layouts}


def _group_by_id(result, group_id: str):
    return next(group for group in result.group_layouts if group.id == group_id)


def _group_bounding(group) -> list[int]:
    return [group.x, group.y, group.width, group.height]


def _diagnostic_codes(result) -> list[str]:
    return [
        diagnostic.code
        for diagnostic in result.diagnostics
        if diagnostic.code.startswith("existing_group_")
    ]


def _existing_group_diagnostics(result):
    return [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code.startswith("existing_group_")
    ]


def _first_group_score(ui: dict) -> dict:
    facts = extract_graph_facts(ui)
    group = facts.scope_furniture[0].groups[0]
    return _score_existing_group(facts, group, classify_layout_facts(facts)).to_json()


def test_compile_layout_plan_preserves_existing_group_when_score_is_coherent() -> None:
    ui = _prompt_pair_ui(group_bounding=[280, 40, 220, 240])
    facts = extract_graph_facts(ui)

    result = compile_layout_plan(_preserve_existing_plan(), facts)

    assert result.ok is True
    assert _node_sections(result)["positive"] == "__existing_root_0__"
    assert _node_sections(result)["negative"] == "__existing_root_0__"
    score = _first_group_score(ui)
    assert score == {
        "scope_path": "",
        "index": 0,
        "title": "Prompts",
        "section_kind": "conditioning",
        "member_refs": [["", "negative"], ["", "positive"]],
        "contained_refs": [["", "negative"], ["", "positive"]],
        "containment": 1.0,
        "topology": 0.0,
        "title_role": 1.0,
        "node_coverage": 1.0,
        "score": 0.75,
        "coherent": True,
    }


def test_compile_layout_plan_dissolves_existing_group_when_containment_is_incoherent() -> None:
    ui = _prompt_pair_ui(group_bounding=[0, 0, 220, 160])
    facts = extract_graph_facts(ui)

    result = compile_layout_plan(_preserve_existing_plan(), facts)

    assert result.ok is True
    assert "__existing_root_0__" not in {group.id for group in result.group_layouts}
    assert _node_sections(result)["positive"] == "__conditioning__"
    assert _node_sections(result)["negative"] == "__conditioning__"
    score = _first_group_score(ui)
    assert score["containment"] == 0.0
    assert score["node_coverage"] == 0.0
    assert score["title_role"] == 1.0
    assert score["coherent"] is False


def test_compile_layout_plan_dissolves_existing_group_when_node_coverage_is_broad() -> None:
    ui = _prompt_pair_ui(group_bounding=[0, 0, 1100, 300])
    facts = extract_graph_facts(ui)

    result = compile_layout_plan(_preserve_existing_plan(), facts)

    assert result.ok is True
    assert "__existing_root_0__" not in {group.id for group in result.group_layouts}
    score = _first_group_score(ui)
    assert score["containment"] == 1.0
    assert score["contained_refs"] == [
        ["", "checkpoint"],
        ["", "negative"],
        ["", "positive"],
        ["", "sample"],
        ["", "save"],
    ]
    assert score["node_coverage"] == 0.4
    assert score["coherent"] is False


def test_compile_layout_plan_applies_existing_group_policy_matrix() -> None:
    ui = _prompt_pair_ui(
        group_bounding=[280, 40, 220, 240],
        group_title="User Prompts",
        group_color="#112233",
    )
    facts = extract_graph_facts(ui)
    plan = _explicit_prompt_pair_plan()
    semantic = compile_layout_plan(
        plan,
        facts,
        options=LayoutCompileOptions(existing_group_policy="force_regroup"),
    )
    semantic_group = _group_by_id(semantic, "conditioning")
    semantic_bounding = _group_bounding(semantic_group)

    preserved = compile_layout_plan(
        plan,
        facts,
        options=LayoutCompileOptions(existing_group_policy="preserve"),
    )
    preserved_group = _group_by_id(preserved, "conditioning")
    assert preserved_group.title == "User Prompts"
    assert preserved_group.color == "#112233"
    assert _group_bounding(preserved_group) == [280, 40, 220, 240]

    renamed = compile_layout_plan(
        plan,
        facts,
        options=LayoutCompileOptions(existing_group_policy="rename_only"),
    )
    renamed_group = _group_by_id(renamed, "conditioning")
    assert renamed_group.title == "Semantic Prompts"
    assert renamed_group.color == "#112233"
    assert _group_bounding(renamed_group) == [280, 40, 220, 240]

    resized = compile_layout_plan(
        plan,
        facts,
        options=LayoutCompileOptions(existing_group_policy="resize_only"),
    )
    resized_group = _group_by_id(resized, "conditioning")
    assert resized_group.title == "User Prompts"
    assert resized_group.color == "#112233"
    assert _group_bounding(resized_group) == semantic_bounding

    renamed_and_resized = compile_layout_plan(
        plan,
        facts,
        options=LayoutCompileOptions(existing_group_policy="rename_and_resize"),
    )
    renamed_and_resized_group = _group_by_id(renamed_and_resized, "conditioning")
    assert renamed_and_resized_group.title == "Semantic Prompts"
    assert renamed_and_resized_group.color == "#112233"
    assert _group_bounding(renamed_and_resized_group) == semantic_bounding

    semantic_preserved = compile_layout_plan(
        plan,
        facts,
        options=LayoutCompileOptions(existing_group_policy="semantic_preserve"),
    )
    semantic_preserved_group = _group_by_id(semantic_preserved, "conditioning")
    assert semantic_preserved_group.title == "User Prompts"
    assert _group_bounding(semantic_preserved_group) == [280, 40, 220, 240]


def test_compile_layout_plan_dissolves_incoherent_groups_with_warning_policy() -> None:
    ui = _prompt_pair_ui(group_bounding=[0, 0, 220, 160])
    facts = extract_graph_facts(ui)

    result = compile_layout_plan(
        _preserve_existing_plan(),
        facts,
        options=LayoutCompileOptions(existing_group_policy="dissolve_with_warning"),
    )

    assert result.ok is True
    assert "__existing_root_0__" not in {group.id for group in result.group_layouts}
    assert _diagnostic_codes(result) == ["existing_group_dissolved"]
    diagnostics = _existing_group_diagnostics(result)
    assert diagnostics[0].severity == "warning"
    assert diagnostics[0].detail["policy"] == "dissolve_with_warning"


def test_compile_layout_plan_force_regroup_rebuilds_incoherent_groups_with_warning() -> None:
    ui = _prompt_pair_ui(group_bounding=[0, 0, 220, 160])
    facts = extract_graph_facts(ui)

    result = compile_layout_plan(
        _preserve_existing_plan(),
        facts,
        options=LayoutCompileOptions(existing_group_policy="force_regroup"),
    )

    assert result.ok is True
    assert "__existing_root_0__" not in {group.id for group in result.group_layouts}
    assert _node_sections(result)["positive"] == "__conditioning__"
    assert _diagnostic_codes(result) == ["existing_group_rebuilt"]
    assert _existing_group_diagnostics(result)[0].detail["policy"] == "force_regroup"


def test_compile_layout_plan_preserves_pinned_nodes_from_ui_unless_force_regrouped() -> None:
    ui = _prompt_pair_ui(group_bounding=[280, 40, 220, 240])
    ui["nodes"][0]["pos"] = [1220, 700]
    ui["nodes"][0]["flags"] = {"pinned": True}
    facts = extract_graph_facts(ui)

    preserved = compile_layout_plan(_explicit_prompt_pair_plan(), facts)
    checkpoint = next(layout for layout in preserved.node_layouts if layout.ref.uid == "checkpoint")
    assert checkpoint.pinned is True
    assert (checkpoint.x, checkpoint.y) == (1220, 700)

    forced = compile_layout_plan(
        _explicit_prompt_pair_plan(),
        facts,
        options=LayoutCompileOptions(
            existing_group_policy="force_regroup",
            pinned_refs=(CanonicalNodeRef("", "checkpoint"),),
        ),
    )
    forced_checkpoint = next(layout for layout in forced.node_layouts if layout.ref.uid == "checkpoint")
    assert forced_checkpoint.pinned is False
    assert (forced_checkpoint.x, forced_checkpoint.y) != (1220, 700)
