from __future__ import annotations

from copy import deepcopy

from vibecomfy.comfy_nodes.agent.layout_reorganisation import (
    REORGANISATION_DECISION_RESULTS,
    REORGANISE_AUTO_ENV,
    decide_post_edit_reorganisation,
    read_reorganise_auto_config,
)


def _base_ui() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [100, 100],
                "size": [180, 80],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sampler"},
                "pos": [420, 100],
                "size": [220, 100],
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
                "widgets_values": [20, 7],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "pos": [820, 100],
                "size": [180, 80],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
        "groups": [
            {
                "title": "Generation",
                "bounding": [50, 50, 1000, 180],
                "nodes": [1, 2, 3],
            }
        ],
    }


def _append_node(ui: dict, node: dict) -> None:
    ui["nodes"].append(node)


def _append_link(
    ui: dict,
    *,
    link_id: int,
    source_id: int,
    target_id: int,
    source_slot: int = 0,
    target_slot: int = 0,
    socket_type: str = "IMAGE",
) -> None:
    ui["links"].append([link_id, source_id, source_slot, target_id, target_slot, socket_type])


def test_default_mode_is_suggest_and_invalid_config_fails_closed_visibly() -> None:
    assert read_reorganise_auto_config({}).mode == "suggest"

    invalid = read_reorganise_auto_config({REORGANISE_AUTO_ENV: "surprise"})

    assert invalid.mode == "off"
    assert invalid.valid is False
    assert "Failing closed to off" in invalid.error

    decision = decide_post_edit_reorganisation(
        _base_ui(),
        _branch_addition_ui(),
        env={REORGANISE_AUTO_ENV: "surprise"},
    )

    assert decision.result == "none"
    assert decision.reason_codes == ("invalid_config", "mode_off")


def test_small_prompt_edit_returns_none_without_layout_noise() -> None:
    before = _base_ui()
    after = deepcopy(before)
    after["nodes"][1]["widgets_values"] = [20, 12345]

    decision = decide_post_edit_reorganisation(before, after, env={})

    assert decision.result == "none"
    assert decision.result in REORGANISATION_DECISION_RESULTS
    assert decision.features is not None
    assert decision.features.nodes_added == 0
    assert decision.features.rewired_links == 0
    assert decision.features.has_edit_magnitude is False


def test_one_node_addition_outside_existing_groups_offers_reorganisation() -> None:
    before = _base_ui()
    after = deepcopy(before)
    _append_node(
        after,
        {
            "id": 4,
            "type": "CLIPTextEncode",
            "class_type": "CLIPTextEncode",
            "properties": {"vibecomfy_uid": "prompt"},
            "pos": [1600, 600],
            "size": [220, 80],
        },
    )

    decision = decide_post_edit_reorganisation(before, after, env={})

    assert decision.result == "offer_reorganisation"
    assert "candidate_boxes_outside_groups" in decision.reason_codes
    assert decision.features is not None
    assert decision.features.added_boxes_outside_groups == 1


def test_off_mode_suppresses_branch_addition_reorganisation_offer() -> None:
    decision = decide_post_edit_reorganisation(
        _base_ui(),
        _branch_addition_ui(),
        env={REORGANISE_AUTO_ENV: "off"},
    )

    assert decision.result == "none"
    assert decision.features is None
    assert decision.reason_codes == ("mode_off",)


def test_branch_addition_offers_reorganisation_in_default_suggest_mode() -> None:
    decision = decide_post_edit_reorganisation(_base_ui(), _branch_addition_ui(), env={})

    assert decision.result == "offer_reorganisation"
    assert "meaningful_graph_growth" in decision.reason_codes
    assert "branch_path_added" in decision.reason_codes
    assert decision.features is not None
    assert decision.features.output_paths_added > 0
    assert decision.features.max_fanout_delta > 0


def test_multi_sampler_edit_prepares_candidate_when_candidate_mode_enabled() -> None:
    decision = decide_post_edit_reorganisation(
        _base_ui(),
        _multi_sampler_ui(),
        env={REORGANISE_AUTO_ENV: "candidate"},
    )

    assert decision.result == "prepare_candidate"
    assert "sampler_path_added" in decision.reason_codes
    assert decision.features is not None
    assert decision.features.samplers_added == 1
    assert decision.features.nodes_added == 2


def test_output_path_addition_offers_reorganisation() -> None:
    before = _base_ui()
    after = deepcopy(before)
    after["nodes"][1]["outputs"][0]["links"].append(12)
    _append_node(
        after,
        {
            "id": 4,
            "type": "SaveImage",
            "class_type": "SaveImage",
            "properties": {"vibecomfy_uid": "save-copy"},
            "pos": [820, 240],
            "size": [180, 80],
            "inputs": [{"name": "images", "type": "IMAGE", "link": 12}],
        },
    )
    _append_link(after, link_id=12, source_id=2, target_id=4)
    after["groups"][0]["bounding"] = [50, 50, 1000, 330]
    after["groups"][0]["nodes"].append(4)

    decision = decide_post_edit_reorganisation(before, after, env={})

    assert decision.result == "offer_reorganisation"
    assert "output_path_added" in decision.reason_codes
    assert decision.features is not None
    assert decision.features.output_nodes_added == 1


def _branch_addition_ui() -> dict:
    after = deepcopy(_base_ui())
    after["nodes"][1]["outputs"][0]["links"].append(12)
    _append_node(
        after,
        {
            "id": 4,
            "type": "PreviewImage",
            "class_type": "PreviewImage",
            "properties": {"vibecomfy_uid": "preview"},
            "pos": [820, 260],
            "size": [180, 80],
            "inputs": [{"name": "images", "type": "IMAGE", "link": 12}],
        },
    )
    _append_link(after, link_id=12, source_id=2, target_id=4)
    after["groups"][0]["bounding"] = [50, 50, 1000, 360]
    after["groups"][0]["nodes"].append(4)
    return after


def _multi_sampler_ui() -> dict:
    after = deepcopy(_base_ui())
    after["nodes"][0]["outputs"][0]["links"].append(12)
    _append_node(
        after,
        {
            "id": 4,
            "type": "KSampler",
            "class_type": "KSampler",
            "properties": {"vibecomfy_uid": "sampler-alt"},
            "pos": [420, 260],
            "size": [220, 100],
            "inputs": [{"name": "image", "type": "IMAGE", "link": 12}],
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [13]}],
        },
    )
    _append_node(
        after,
        {
            "id": 5,
            "type": "SaveImage",
            "class_type": "SaveImage",
            "properties": {"vibecomfy_uid": "save-alt"},
            "pos": [820, 270],
            "size": [180, 80],
            "inputs": [{"name": "images", "type": "IMAGE", "link": 13}],
        },
    )
    _append_link(after, link_id=12, source_id=1, target_id=4)
    _append_link(after, link_id=13, source_id=4, target_id=5)
    after["groups"][0]["bounding"] = [50, 50, 1000, 390]
    after["groups"][0]["nodes"].extend([4, 5])
    return after
