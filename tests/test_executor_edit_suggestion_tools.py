"""B5/B14 tests for advisory edit-target and seed-suggestion tools."""

from __future__ import annotations

from typing import Any

import pytest

from vibecomfy.executor.edit_suggestion_tools import (
    diagnose_existing_tweak_ranking,
    rank_edit_targets,
    suggest_seed_nodes,
)
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus

# Imperative/directive language that must never appear in candidate reasons,
# factor details, or factor names. "edit target" as a noun phrase is allowed;
# instructions like "you must edit X" are not.
_DIRECTIVE_TOKENS = (
    "must",
    "should",
    "do not",
    "don't",
    "you need",
    "land ",
    "stop ",
    "only way",
    "never ",
    "please ",
)


def _node(class_type: str, **kwargs: Any) -> dict[str, Any]:
    node: dict[str, Any] = {"class_type": class_type}
    node.update(kwargs)
    return node


def _graph(*nodes: dict[str, Any]) -> dict[str, Any]:
    return {"nodes": list(nodes)}


def _assert_non_directive(text: str) -> None:
    lowered = text.casefold()
    assert not any(token in lowered for token in _DIRECTIVE_TOKENS), text


def _payload(result: ToolResult) -> dict[str, Any]:
    """Thawed (JSON-safe) result payload for content assertions."""

    return result.to_dict()["result"]


# ── explicit-call gate ───────────────────────────────────────────────────────


def test_all_suggestion_tools_refuse_implicit_calls() -> None:
    graph = _graph(_node("KSampler", widgets_values=[20, 5, 42]))
    results = (
        rank_edit_targets(graph, "increase steps"),
        suggest_seed_nodes("upscale an image", {}),
        diagnose_existing_tweak_ranking(graph, "increase steps"),
    )
    for result in results:
        assert result.status is ToolStatus.REFUSED
        assert result.diagnostics[0].code == "suggestion_tool_requires_explicit_call"
        assert result.result is None


def test_explicit_calls_run_and_return_typed_results() -> None:
    graph = _graph(_node("KSampler", widgets_values=[20, 5, 42]))
    ranked = rank_edit_targets(graph, "increase steps", explicit=True)
    assert ranked.status is ToolStatus.OK
    assert ranked.result["case"] == "existing-node"

    seeded = suggest_seed_nodes("upscale an image", {}, explicit=True)
    assert seeded.status is ToolStatus.OK
    assert seeded.result["case"] == "empty-graph"

    diagnosed = diagnose_existing_tweak_ranking(graph, "increase steps", explicit=True)
    assert diagnosed.status is ToolStatus.OK
    assert diagnosed.result["case"] == "existing-node"


@pytest.mark.parametrize(
    "call",
    [
        lambda: rank_edit_targets(_graph(_node("KSampler")), "   ", explicit=True),
        lambda: suggest_seed_nodes("   ", {}, explicit=True),
        lambda: diagnose_existing_tweak_ranking(_graph(_node("KSampler")), "   ", explicit=True),
    ],
)
def test_suggestion_tools_reject_empty_query_text(call) -> None:
    result = call()
    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.result is None


def test_suggestion_tools_reject_bad_max_counts() -> None:
    graph = _graph(_node("KSampler", widgets_values=[20]))
    assert (
        rank_edit_targets(graph, "tweak seed", explicit=True, max_targets=0).status
        is ToolStatus.INVALID_REQUEST
    )
    assert (
        suggest_seed_nodes("upscale", {}, explicit=True, max_suggestions=-1).status
        is ToolStatus.INVALID_REQUEST
    )


# ── rank_edit_targets typed cases ────────────────────────────────────────────


@pytest.mark.parametrize("graph", [None, {}, {"nodes": []}, {"nodes": None}])
def test_rank_edit_targets_empty_graph_case(graph: Any) -> None:
    result = rank_edit_targets(graph, "increase steps", explicit=True)
    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["case"] == "empty-graph"
    assert _payload(result)["candidates"] == []
    assert result.result["reason"]


def test_rank_edit_targets_no_candidate_case() -> None:
    # Nodes exist, but none exposes editable fields: an unknown class with
    # only connected inputs, plus a class-less node.
    graph = _graph(
        _node("ZZZ_Unknown_ZZZ", inputs={"image": [1, 0, {"image": "x.png"}]}),
        {"type": ""},
    )
    result = rank_edit_targets(graph, "increase steps", explicit=True)
    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["case"] == "no-candidate"
    assert _payload(result)["candidates"] == []


def test_rank_edit_targets_existing_node_exposes_scores_factors_and_reasons() -> None:
    graph = _graph(_node("KSampler", id=1, widgets_values=[20, 5, 42]))
    result = rank_edit_targets(graph, "increase steps to 30", explicit=True)
    assert result.status is ToolStatus.OK
    payload = result.result
    assert payload["case"] == "existing-node"
    assert payload["total_nodes"] == 1

    candidate = payload["candidates"][0]
    assert candidate["class_type"] == "KSampler"
    assert candidate["node_id"] == "1"
    assert candidate["score"] == sum(f["points"] for f in candidate["factors"])
    factor_names = {f["name"] for f in candidate["factors"]}
    assert "editable_fields" in factor_names
    assert "field_parameter_term" in factor_names
    assert candidate["reason"]


def test_rank_edit_targets_orders_by_intent_relevance() -> None:
    graph = _graph(
        _node("KSampler", id=1, widgets_values=[20, 5, 42]),
        _node("ImageScaleBy", id=2, widgets={"upscale_method": "lanczos", "scale_by": 1.5}),
        _node("SaveVideo", id=3, widgets_values=["out.mp4", "h264"]),
    )
    result = rank_edit_targets(graph, "upscale the image", explicit=True, max_targets=2)
    classes = [c["class_type"] for c in _payload(result)["candidates"]]
    assert classes == ["ImageScaleBy", "KSampler"]
    scores = [c["score"] for c in result.result["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_rank_edit_targets_controlnet_heuristic_factor() -> None:
    graph = _graph(
        _node("ACN_AdvancedControlNetApply", id=9, widgets={"strength": 0.8}),
        _node("KSampler", id=1, widgets_values=[20, 5, 42]),
    )
    result = rank_edit_targets(graph, "increase controlnet strength", explicit=True)
    candidates = {c["class_type"]: c for c in result.result["candidates"]}
    acn = candidates["ACN_AdvancedControlNetApply"]
    names = {f["name"] for f in acn["factors"]}
    assert "controlnet_heuristic" in names
    assert acn["score"] == sum(f["points"] for f in acn["factors"])
    assert acn["score"] > candidates["KSampler"]["score"]


def test_rank_edit_targets_penalizes_output_sink_nodes() -> None:
    graph = _graph(_node("SaveVideo", id=3, widgets_values=["out.mp4", "h264"]))
    result = rank_edit_targets(graph, "change the video format", explicit=True)
    candidate = result.result["candidates"][0]
    names = {f["name"] for f in candidate["factors"]}
    assert "non_editable_sink" in names
    assert any(f["points"] < 0 for f in candidate["factors"])


def test_rank_edit_targets_max_targets_limits_candidates() -> None:
    graph = _graph(
        _node("KSampler", id=1, widgets_values=[20, 5, 42]),
        _node("KSampler", id=2, widgets_values=[20, 5, 42]),
        _node("KSampler", id=3, widgets_values=[20, 5, 42]),
    )
    result = rank_edit_targets(graph, "tweak seed", explicit=True, max_targets=2)
    assert result.result["total_nodes"] == 3
    assert len(result.result["candidates"]) == 2


def test_rank_edit_targets_accepts_mapping_nodes_container() -> None:
    graph = {
        "nodes": {
            "sampler": _node("KSampler", widgets_values=[20, 5, 42]),
            "scale": _node("ImageScaleBy", widgets={"scale_by": 1.5}),
        }
    }
    result = rank_edit_targets(graph, "tweak seed", explicit=True)
    assert result.status is ToolStatus.OK
    assert result.result["total_nodes"] == 2
    node_ids = {c["node_id"] for c in result.result["candidates"]}
    assert node_ids == {"sampler", "scale"}


# ── suggest_seed_nodes typed cases and constraints ──────────────────────────


def test_suggest_seed_nodes_empty_graph_case() -> None:
    result = suggest_seed_nodes("upscale an image", {}, explicit=True)
    assert result.status is ToolStatus.OK
    assert result.result["case"] == "empty-graph"
    classes = {s["class_type"] for s in result.result["suggestions"]}
    assert "ImageUpscaleWithModel" in classes
    assert _payload(result)["matched_phrases"] == ["upscale"]


def test_suggest_seed_nodes_existing_node_case_when_graph_has_nodes() -> None:
    graph = _graph(_node("KSampler", widgets_values=[20]))
    result = suggest_seed_nodes("upscale an image", {}, graph=graph, explicit=True)
    assert result.status is ToolStatus.OK
    assert result.result["case"] == "existing-node"


def test_suggest_seed_nodes_no_candidate_case() -> None:
    result = suggest_seed_nodes("teleport the quasar", {}, explicit=True)
    assert result.status is ToolStatus.NO_RESULTS
    assert result.result["case"] == "no-candidate"
    assert _payload(result)["suggestions"] == []
    assert result.result["reason"]


def test_suggest_seed_nodes_preferred_and_exclude_constraints() -> None:
    result = suggest_seed_nodes(
        "upscale a video",
        {
            "output_type": "video",
            "preferred_classes": ["SaveVideo"],
            "exclude_classes": ["ImageScale"],
        },
        explicit=True,
    )
    classes = [s["class_type"] for s in result.result["suggestions"]]
    assert "SaveVideo" in classes
    assert not any("ImageScale" in class_type for class_type in classes)

    save_video = next(s for s in result.result["suggestions"] if s["class_type"] == "SaveVideo")
    names = {f["name"] for f in save_video["factors"]}
    assert "preferred_class" in names
    assert "output_type_match" in names
    assert save_video["score"] == sum(f["points"] for f in save_video["factors"])
    # Constraint tilts override the plain capability ranking.
    assert classes[0] == "SaveVideo"


def test_suggest_seed_nodes_output_type_mismatch_is_penalized() -> None:
    result = suggest_seed_nodes(
        "upscale an image",
        {"output_type": "video"},
        explicit=True,
    )
    suggestions = {s["class_type"]: s for s in result.result["suggestions"]}
    assert any(f["name"] == "output_type_mismatch" for f in suggestions["ImageUpscaleWithModel"]["factors"])


@pytest.mark.parametrize(
    "constraints",
    [
        {"output_type": 7},
        {"preferred_classes": "KSampler"},
        {"exclude_classes": [3]},
        "video",
    ],
)
def test_suggest_seed_nodes_rejects_bad_constraints(constraints: Any) -> None:
    result = suggest_seed_nodes("upscale", constraints, explicit=True)
    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.result is None


# ── advisory-only contract ──────────────────────────────────────────────────


def test_candidate_reasons_and_factor_details_are_never_directive() -> None:
    graph = _graph(
        _node("KSampler", id=1, widgets={"steps": 20, "cfg": 5, "seed": 42}),
        _node("ACN_AdvancedControlNetApply", id=2, widgets={"strength": 0.8}),
        _node("ImageScaleBy", id=3, widgets={"scale_by": 1.5}),
        _node("SaveVideo", id=4, widgets_values=["out.mp4", "h264"]),
    )
    ranked = rank_edit_targets(
        graph, "increase controlnet strength and upscale the image", explicit=True
    )
    assert ranked.result["candidates"]
    for candidate in ranked.result["candidates"]:
        _assert_non_directive(candidate["reason"])
        for factor in candidate["factors"]:
            _assert_non_directive(factor["name"])
            _assert_non_directive(factor["detail"])

    seeded = suggest_seed_nodes(
        "make a video with controlnet", {"output_type": "video"}, explicit=True
    )
    assert seeded.result["suggestions"]
    for suggestion in seeded.result["suggestions"]:
        _assert_non_directive(suggestion["reason"])
        for factor in suggestion["factors"]:
            _assert_non_directive(factor["name"])
            _assert_non_directive(factor["detail"])


def test_suggestion_results_round_trip_as_typed_tool_results() -> None:
    graph = _graph(_node("KSampler", id=1, widgets_values=[20, 5, 42]))
    ranked = rank_edit_targets(graph, "tweak seed", explicit=True)
    restored = ToolResult.from_dict(ranked.to_dict())
    assert restored.to_dict() == ranked.to_dict()

    seeded = suggest_seed_nodes("upscale a video", {"output_type": "video"}, explicit=True)
    restored = ToolResult.from_dict(seeded.to_dict())
    assert restored.to_dict() == seeded.to_dict()


# ── optional diagnostic parity with the legacy ranking ──────────────────────


def test_diagnose_existing_tweak_ranking_matches_legacy_source() -> None:
    legacy = pytest.importorskip(
        "vibecomfy.comfy_nodes.agent._frag_batch_memory",
        reason="legacy ranking module unavailable in this environment",
    )
    graph = _graph(
        _node("KSampler", id=1, widgets={"steps": 20, "cfg": 5, "seed": 42}),
        _node("ACN_AdvancedControlNetApply", id=2, widgets={"strength": 0.8}),
        _node("SaveVideo", id=3, widgets_values=["out.mp4", "h264"]),
    )
    query = "increase controlnet strength"
    legacy_targets = legacy._existing_parameter_tweak_targets_from_graph(
        graph, query_text=query.casefold(), seen_targets=set()
    )
    assert legacy_targets, "legacy ranking must produce targets for the fixture"

    result = diagnose_existing_tweak_ranking(graph, query, explicit=True)
    assert result.status is ToolStatus.OK
    assert result.result["case"] == "existing-node"
    pairs = [(item["score"], item["target"]) for item in _payload(result)["targets"]]
    assert pairs == legacy_targets
    # Targets carry the legacy "{class_type} [{node_id}] ({preview})" shape.
    assert result.result["targets"][0]["target"].startswith("KSampler [1] (")
    assert result.result["legacy_format"] == "{class_type} [{node_id}] ({preview})"


def test_diagnose_existing_tweak_ranking_typed_cases() -> None:
    empty = diagnose_existing_tweak_ranking({}, "increase steps", explicit=True)
    assert empty.status is ToolStatus.NO_RESULTS
    assert empty.result["case"] == "empty-graph"

    no_candidate = diagnose_existing_tweak_ranking(
        _graph(_node("ZZZ_Unknown_ZZZ")), "increase steps", explicit=True
    )
    assert no_candidate.status is ToolStatus.NO_RESULTS
    assert no_candidate.result["case"] == "no-candidate"
