"""Reusable HotShotXL/AnimateDiff graph fixtures for execution-plan tests.

These fixtures intentionally stay as small LiteGraph-shaped dictionaries.  They
do not import agent batch-loop or routing code; callers can pair them with the
pure execution-plan evaluator directly.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from vibecomfy.comfy_nodes.agent.execution_plan import ExecutionPlan, PlanCondition, SocketRef


HOTSHOTXL_MOTION_NODE = 10
ANIMATEDIFF_APPLY_NODE = 11
LATENT_NODE = 12
SAMPLER_NODE = 13
VAE_DECODE_NODE = 14
VIDEO_TERMINAL_NODE = 15


def _node(
    node_id: int,
    class_type: str,
    *,
    inputs: list[dict[str, Any]] | None = None,
    outputs: list[dict[str, Any]] | None = None,
    widgets_values: list[Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": node_id,
        "type": class_type,
        "class_type": class_type,
    }
    if inputs is not None:
        payload["inputs"] = inputs
    if outputs is not None:
        payload["outputs"] = outputs
    if widgets_values is not None:
        payload["widgets_values"] = widgets_values
    return payload


def _input(name: str, slot_type: str, link: int | None = None) -> dict[str, Any]:
    return {"name": name, "type": slot_type, "link": link}


def _output(name: str, slot_type: str, links: list[int] | None = None) -> dict[str, Any]:
    return {"name": name, "type": slot_type, "links": links or []}


def _link(
    link_id: int,
    origin_node: int,
    origin_slot: int,
    target_node: int,
    target_slot: int,
    link_type: str,
) -> list[Any]:
    return [link_id, origin_node, origin_slot, target_node, target_slot, link_type]


def _complete_video_graph() -> dict[str, Any]:
    return {
        "nodes": [
            _node(
                1,
                "CheckpointLoaderSimple",
                outputs=[
                    _output("MODEL", "MODEL", [1]),
                    _output("CLIP", "CLIP", [2, 3]),
                    _output("VAE", "VAE", [4]),
                ],
                widgets_values=["sdxl_base.safetensors"],
            ),
            _node(
                2,
                "CLIPTextEncode",
                inputs=[_input("clip", "CLIP", 2)],
                outputs=[_output("CONDITIONING", "CONDITIONING", [5])],
                widgets_values=["a small robot walking"],
            ),
            _node(
                3,
                "CLIPTextEncode",
                inputs=[_input("clip", "CLIP", 3)],
                outputs=[_output("CONDITIONING", "CONDITIONING", [6])],
                widgets_values=["blur"],
            ),
            _node(
                HOTSHOTXL_MOTION_NODE,
                "HotshotXLLoader",
                outputs=[_output("MOTION_MODEL", "MOTION_MODEL", [7])],
                widgets_values=["hotshotxl_mm.safetensors"],
            ),
            _node(
                ANIMATEDIFF_APPLY_NODE,
                "ADE_AnimateDiffLoaderWithContext",
                inputs=[
                    _input("model", "MODEL", 1),
                    _input("motion_model", "MOTION_MODEL", 7),
                ],
                outputs=[_output("MODEL", "MODEL", [8])],
            ),
            _node(
                LATENT_NODE,
                "EmptyLatentImage",
                outputs=[_output("LATENT", "LATENT", [9])],
                widgets_values=[512, 512, 8],
            ),
            _node(
                SAMPLER_NODE,
                "KSampler",
                inputs=[
                    _input("model", "MODEL", 8),
                    _input("positive", "CONDITIONING", 5),
                    _input("negative", "CONDITIONING", 6),
                    _input("latent_image", "LATENT", 9),
                ],
                outputs=[_output("LATENT", "LATENT", [10])],
                widgets_values=[1234, 20, 7.5, "euler", "normal", 1.0],
            ),
            _node(
                VAE_DECODE_NODE,
                "VAEDecode",
                inputs=[_input("samples", "LATENT", 10), _input("vae", "VAE", 4)],
                outputs=[_output("IMAGE", "IMAGE", [11])],
            ),
            _node(
                VIDEO_TERMINAL_NODE,
                "VHS_VideoCombine",
                inputs=[_input("images", "IMAGE", 11)],
                widgets_values=[8, 8.0, "video/hotshotxl"],
            ),
        ],
        "links": [
            _link(1, 1, 0, ANIMATEDIFF_APPLY_NODE, 0, "MODEL"),
            _link(2, 1, 1, 2, 0, "CLIP"),
            _link(3, 1, 1, 3, 0, "CLIP"),
            _link(4, 1, 2, VAE_DECODE_NODE, 1, "VAE"),
            _link(5, 2, 0, SAMPLER_NODE, 1, "CONDITIONING"),
            _link(6, 3, 0, SAMPLER_NODE, 2, "CONDITIONING"),
            _link(7, HOTSHOTXL_MOTION_NODE, 0, ANIMATEDIFF_APPLY_NODE, 1, "MOTION_MODEL"),
            _link(8, ANIMATEDIFF_APPLY_NODE, 0, SAMPLER_NODE, 0, "MODEL"),
            _link(9, LATENT_NODE, 0, SAMPLER_NODE, 3, "LATENT"),
            _link(10, SAMPLER_NODE, 0, VAE_DECODE_NODE, 0, "LATENT"),
            _link(11, VAE_DECODE_NODE, 0, VIDEO_TERMINAL_NODE, 0, "IMAGE"),
        ],
    }


def structurally_complete_video_graph() -> dict[str, Any]:
    """HotShotXL/AnimateDiff path produces 8 frames consumed by a video terminal."""

    return deepcopy(_complete_video_graph())


def disconnected_sidecar_graph() -> dict[str, Any]:
    """HotShotXL sidecar exists beside an unrelated active image output chain."""

    return {
        "nodes": [
            _node(
                1,
                "LoadImage",
                outputs=[_output("IMAGE", "IMAGE", [1])],
                widgets_values=["input.png"],
            ),
            _node(
                2,
                "SaveImage",
                inputs=[_input("images", "IMAGE", 1)],
                widgets_values=["output"],
            ),
            _node(
                HOTSHOTXL_MOTION_NODE,
                "HotshotXLLoader",
                outputs=[_output("MOTION_MODEL", "MOTION_MODEL", [2])],
                widgets_values=["hotshotxl_mm.safetensors"],
            ),
            _node(
                ANIMATEDIFF_APPLY_NODE,
                "ADE_AnimateDiffLoaderWithContext",
                inputs=[_input("motion_model", "MOTION_MODEL", 2)],
                outputs=[_output("MODEL", "MODEL", [])],
            ),
        ],
        "links": [
            _link(1, 1, 0, 2, 0, "IMAGE"),
            _link(2, HOTSHOTXL_MOTION_NODE, 0, ANIMATEDIFF_APPLY_NODE, 0, "MOTION_MODEL"),
        ],
    }


def missing_active_8_frame_path_graph() -> dict[str, Any]:
    """An 8-frame latent exists, but the active sampler path uses a 1-frame latent."""

    graph = _complete_video_graph()
    graph["nodes"] = [
        _node(
            99,
            "EmptyLatentImage",
            outputs=[_output("LATENT", "LATENT", [])],
            widgets_values=[512, 512, 8],
        )
        if node["id"] == LATENT_NODE
        else node
        for node in graph["nodes"]
    ]
    graph["nodes"].append(
        _node(
            LATENT_NODE,
            "EmptyLatentImage",
            outputs=[_output("LATENT", "LATENT", [9])],
            widgets_values=[512, 512, 1],
        )
    )
    return graph


def missing_connected_video_terminal_graph() -> dict[str, Any]:
    """HotShotXL reaches decoded images, but only an image terminal consumes them."""

    graph = _complete_video_graph()
    graph["nodes"] = [
        _node(
            VIDEO_TERMINAL_NODE,
            "SaveImage",
            inputs=[_input("images", "IMAGE", 11)],
            widgets_values=["hotshotxl/frame"],
        )
        if node["id"] == VIDEO_TERMINAL_NODE
        else node
        for node in graph["nodes"]
    ]
    return graph


def hotshotxl_video_execution_plan() -> ExecutionPlan:
    """Plan conditions shared by HotShotXL evaluator tests."""

    hotshotxl = SocketRef(node_id=str(HOTSHOTXL_MOTION_NODE), class_type="HotshotXLLoader")
    latent_8 = SocketRef(node_id=str(LATENT_NODE), class_type="EmptyLatentImage")
    terminal = SocketRef(node_id=str(VIDEO_TERMINAL_NODE), class_type="VHS_VideoCombine")
    decoder = SocketRef(node_id=str(VAE_DECODE_NODE), class_type="VAEDecode")
    return ExecutionPlan(
        plan_id="hotshotxl-video",
        goal="Generate an active 8-frame HotShotXL video output.",
        selected_precedent_id="precedent-hotshotxl-8f",
        done_conditions=(
            PlanCondition(
                condition_id="hotshotxl.loader.present",
                kind="required_class",
                class_type="HotshotXLLoader",
            ),
            PlanCondition(
                condition_id="animatediff.present",
                kind="required_class",
                class_type="ADE_AnimateDiffLoaderWithContext",
            ),
            PlanCondition(
                condition_id="hotshotxl.8_frames",
                kind="batch_frame_count",
                source=latent_8,
                expected=8,
                details={"field": "widget_2"},
                message="HotShotXL must use an active 8-frame latent path.",
            ),
            PlanCondition(
                condition_id="hotshotxl.reaches_video_terminal",
                kind="reachable_path",
                source=hotshotxl,
                target=terminal,
                message="HotShotXL/AnimateDiff output must reach the video terminal.",
            ),
            PlanCondition(
                condition_id="video.terminal.consumes_decoded_frames",
                kind="terminal_consumes",
                source=decoder,
                target=terminal,
                input_name="images",
                message="A connected video terminal must consume decoded frames.",
            ),
            PlanCondition(
                condition_id="video.output_domain.active",
                kind="active_output_domain",
                expected="VIDEO",
                message="The active terminal output must be video-domain.",
            ),
        ),
    )


@pytest.fixture
def complete_hotshotxl_video_graph() -> dict[str, Any]:
    return structurally_complete_video_graph()


@pytest.fixture
def disconnected_hotshotxl_sidecar_graph() -> dict[str, Any]:
    return disconnected_sidecar_graph()


@pytest.fixture
def hotshotxl_missing_active_8_frame_path_graph() -> dict[str, Any]:
    return missing_active_8_frame_path_graph()


@pytest.fixture
def hotshotxl_missing_connected_video_terminal_graph() -> dict[str, Any]:
    return missing_connected_video_terminal_graph()


@pytest.fixture
def hotshotxl_plan() -> ExecutionPlan:
    return hotshotxl_video_execution_plan()


__all__ = (
    "complete_hotshotxl_video_graph",
    "disconnected_hotshotxl_sidecar_graph",
    "disconnected_sidecar_graph",
    "hotshotxl_missing_active_8_frame_path_graph",
    "hotshotxl_missing_connected_video_terminal_graph",
    "hotshotxl_plan",
    "hotshotxl_video_execution_plan",
    "missing_active_8_frame_path_graph",
    "missing_connected_video_terminal_graph",
    "structurally_complete_video_graph",
)
