from __future__ import annotations

from vibecomfy.executor import core as executor_core
from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
from vibecomfy.executor.layout_hints import build_classify_layout_hint
from vibecomfy.executor.profiles import AgentSpecShape
from vibecomfy.executor.prompts import build_classify_messages


def _bad_layout_ui() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [100, 100],
                "size": [300, 100],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "pos": [50, 110],
                "size": [300, 100],
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "pos": [80, 120],
                "size": [300, 100],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
            {
                "id": 4,
                "type": "Reroute",
                "class_type": "Reroute",
                "properties": {"vibecomfy_uid": "reroute"},
                "pos": [900, 900],
                "size": [40, 40],
                "inputs": [{"name": "", "type": "*", "link": 12}],
                "outputs": [{"name": "", "type": "*", "links": [13]}],
            },
            {
                "id": 5,
                "type": "PreviewImage",
                "class_type": "PreviewImage",
                "properties": {"vibecomfy_uid": "preview"},
                "pos": [170, 130],
                "size": [300, 100],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 13}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
            [12, 1, 0, 4, 0, "IMAGE"],
            [13, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [
            {
                "title": "Too small",
                "bounding": [0, 0, 200, 140],
                "nodes": [1, 2],
            }
        ],
    }


def _readable_layout_ui() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [0, 0],
                "size": [160, 80],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "pos": [320, 0],
                "size": [160, 80],
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "pos": [640, 0],
                "size": [160, 80],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
        "groups": [],
    }


def test_bad_layout_hint_exposes_compact_poor_layout_evidence() -> None:
    hint = build_classify_layout_hint(_bad_layout_ui())
    cached = build_classify_layout_hint(_bad_layout_ui())

    assert hint is not None
    assert cached is hint
    assert hint.verdict == "needs_reorganise"
    assert hint.overlap_signal == "count=6"
    assert hint.backward_edge_signal == "high_ratio=0.3333"
    assert hint.spacing_group_helper_signal.startswith(
        "spacing=high_density:"
    )
    assert "group=low_coherence:" in hint.spacing_group_helper_signal
    assert "helper=far:1" in hint.spacing_group_helper_signal
    assert hint.review_hostile is True


def test_readable_layout_hint_stays_non_hostile() -> None:
    hint = build_classify_layout_hint(_readable_layout_ui())

    assert hint is not None
    assert hint.verdict == "ok"
    assert hint.overlap_signal == "none"
    assert hint.backward_edge_signal == "ratio=0"
    assert hint.review_hostile is False


def test_classify_prompt_renders_layout_hint_as_advisory_only() -> None:
    hint = build_classify_layout_hint(_bad_layout_ui())
    assert hint is not None

    messages = build_classify_messages(
        "change the sampler seed to 4",
        has_graph=True,
        graph_summary="5 node(s): LoadImage, KSampler, SaveImage",
        layout_hint=hint.to_prompt_fields(),
    )
    user_content = messages[1]["content"]

    assert "Deterministic layout hint" in user_content
    assert "advisory" in user_content
    assert "do not route concrete functional edits to reorganise solely from this hint" in user_content
    assert "verdict=needs_reorganise" in user_content
    assert "overlap=count=6" in user_content
    assert "backward_edges=high_ratio=0.3333" in user_content
    assert "review_hostile=true" in user_content
    assert hint.graph_hash not in user_content
    assert "pairs" not in user_content


def test_executor_threads_compact_layout_hint_into_classify_messages(monkeypatch) -> None:
    captured: dict = {}

    def fake_run_classify_turn(query: str, **kwargs):
        captured.update(kwargs)
        return ClassifyDecision(route="respond", task="respond")

    monkeypatch.setattr(executor_core, "run_classify_turn", fake_run_classify_turn)

    result = executor_core._run_classify(
        ExecutorRequest(query="change the sampler seed to 4", graph=_bad_layout_ui()),
        AgentSpecShape(agent="hermes", model="test"),
    )

    assert result.route == "respond"
    messages = captured.get("messages")
    assert isinstance(messages, list)
    user_content = messages[1]["content"]
    assert "Deterministic layout hint" in user_content
    assert "verdict=needs_reorganise" in user_content
    assert "review_hostile=true" in user_content
    assert "graph_hash" not in user_content
