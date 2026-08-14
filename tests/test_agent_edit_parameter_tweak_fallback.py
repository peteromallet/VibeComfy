from __future__ import annotations

from vibecomfy.executor.edit_suggestion_tools import (
    rank_edit_targets,
    suggest_seed_nodes,
)
from vibecomfy.executor.tool_contracts import ToolStatus


def _ks_graph() -> dict:
    return {
        "nodes": {
            "3": {
                "id": 3,
                "type": "KSampler",
                "widgets_values": [
                    156680208700286,
                    "fixed",
                    20,
                    8.0,
                    "euler",
                    "normal",
                    1.0,
                ],
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 1},
                    {"name": "positive", "type": "CONDITIONING", "link": 2},
                    {"name": "negative", "type": "CONDITIONING", "link": 3},
                    {"name": "latent_image", "type": "LATENT", "link": 4},
                ],
            }
        }
    }


def test_rank_edit_targets_requires_an_explicit_agent_call() -> None:
    result = rank_edit_targets(_ks_graph(), "increase steps", explicit=False)

    assert result.status is ToolStatus.REFUSED
    assert result.result is None


def test_rank_edit_targets_returns_semantic_fields_when_called_explicitly() -> None:
    result = rank_edit_targets(_ks_graph(), "increase steps and adjust cfg", explicit=True)

    assert result.status is ToolStatus.OK
    candidates = result.result["candidates"]
    assert candidates
    candidate = candidates[0]
    assert candidate["class_type"] == "KSampler"
    assert "seed" in candidate["preview"]
    assert "steps" in candidate["preview"]
    assert "cfg" in candidate["preview"]
    assert "denoise" in candidate["preview"]
    assert "widget_0" not in candidate["preview"]


def test_rank_edit_targets_keeps_enum_annotations_bounded() -> None:
    result = rank_edit_targets(_ks_graph(), "change sampler", explicit=True)

    preview = result.result["candidates"][0]["preview"]
    assert "control_after_generate[" in preview
    assert any(value in preview for value in ("fixed", "randomize", "increment", "decrement"))


def test_unknown_node_uses_advisory_widget_fallback_only_after_explicit_call() -> None:
    graph = {
        "nodes": {
            "99": {
                "id": "99",
                "class_type": "UnknownCustomNode",
                "inputs": {},
                "widgets": {"widget_3": 7, "widget_6": 100},
            }
        }
    }

    result = rank_edit_targets(graph, "increase frame count", explicit=True)

    assert result.status is ToolStatus.OK
    assert "widget_3" in result.result["candidates"][0]["preview"]


def test_seed_suggestions_require_an_explicit_agent_call() -> None:
    refused = suggest_seed_nodes("text to image", {}, explicit=False)
    accepted = suggest_seed_nodes("text to image", {}, explicit=True)

    assert refused.status is ToolStatus.REFUSED
    assert refused.result is None
    assert accepted.status is ToolStatus.OK
    assert {item["class_type"] for item in accepted.result["suggestions"]} >= {
        "CLIPTextEncode",
        "KSampler",
        "VAEDecode",
    }
