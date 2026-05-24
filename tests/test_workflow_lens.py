"""Lens integration tests covering generic graph behaviour and
first/last conditioning on the LTX parity template.

All intent assertions in this module operate through the
:mod:`vibecomfy.lens` layer without reaching for compiled Comfy API
JSON link checks.
"""

from __future__ import annotations

import pytest

from vibecomfy.lens import (
    diagnostics,
    edge_source,
    edge_targets,
    lens,
    node_value,
    nodes_by_class_type,
    outputs,
    registered_input_target,
    upstream,
    downstream,
)
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


# ── helpers ────────────────────────────────────────────────────────────────


def _tiny_first_last_workflow() -> VibeWorkflow:
    """Build a tiny (8-node) workflow that mimics a stripped-down first/last
    conditioning pattern so lens queries can be exercised on a predictable
    graph with known edge topology."""
    wf = VibeWorkflow(
        "tiny/first_last_smoke",
        WorkflowSource(id="tiny/first_last_smoke", source_type="fixture"),
    )

    # Use wf.node() for builder pattern (it supports Handle connections)
    start_img = wf.node("LoadImage", image="start.png")
    end_img = wf.node("LoadImage", image="end.png")

    resize = wf.node(
        "ResizeImageMaskNode",
        widget_0="scale longer dimension",
        widget_1=256,
        widget_2="lanczos",
        input=start_img.out(0),
    )
    condition = wf.node(
        "LTXVImgToVideoConditionOnly",
        widget_0=1.0,
        widget_1=False,
        image=resize.out(0),
    )

    resize2 = wf.node(
        "ResizeImageMaskNode",
        widget_0="scale longer dimension",
        widget_1=256,
        widget_2="lanczos",
        input=end_img.out(0),
    )
    condition2 = wf.node(
        "LTXVImgToVideoConditionOnly",
        widget_0=1.0,
        widget_1=False,
        image=resize2.out(0),
    )

    wf.finalize_metadata()
    wf.register_input("start_image", start_img.node.id, "image", "start.png")
    wf.register_input("end_image", end_img.node.id, "image", "end.png")
    wf.register_input("first_frame_strength", condition.node.id, "widget_0", 1.0)
    wf.register_input("last_frame_strength", condition2.node.id, "widget_0", 1.0)
    return wf


# ── generic lens behaviour ────────────────────────────────────────────────


def test_lens_edge_source_on_tiny_workflow() -> None:
    """edge_source resolves conditioning edges on a tiny authored graph."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    # The first LTXVImgToVideoConditionOnly should have its .image input fed
    # by the ResizeImageMaskNode.
    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    assert len(cond_nodes) == 2

    # First condition node gets its image from a ResizeImageMaskNode
    src0 = l.edge_source(cond_nodes[0].id, "image")
    assert src0 is not None
    assert wf.nodes[src0.from_node].class_type == "ResizeImageMaskNode"

    # Second condition node also gets its image from a ResizeImageMaskNode
    src1 = l.edge_source(cond_nodes[1].id, "image")
    assert src1 is not None
    assert wf.nodes[src1.from_node].class_type == "ResizeImageMaskNode"

    # The two ResizeImageMaskNode sources should be distinct
    assert src0.from_node != src1.from_node


def test_lens_edge_source_returns_none_for_widget_input() -> None:
    """edge_source returns None when the input is widget-fed, not edge-fed."""
    wf = _tiny_first_last_workflow()

    # widget_0 on a condition node is a static value, not an edge
    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    assert lens(wf).edge_source(cond_nodes[0].id, "widget_0") is None


def test_lens_edge_targets_on_tiny_workflow() -> None:
    """edge_targets enumerates downstream sinks from a source node."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    # Every ResizeImageMaskNode feeds exactly one LTXVImgToVideoConditionOnly
    resize_nodes = nodes_by_class_type(wf, "ResizeImageMaskNode")
    assert len(resize_nodes) == 2

    for rn in resize_nodes:
        targets = l.edge_targets(rn.id)
        assert len(targets) == 1
        assert wf.nodes[targets[0].to_node].class_type == "LTXVImgToVideoConditionOnly"


def test_lens_upstream_downstream_on_tiny_workflow() -> None:
    """upstream/downstream produce correct one-level traversal sets."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    for cn in cond_nodes:
        up = l.upstream(cn.id)
        assert len(up) == 1
        up_node_id = next(iter(up))
        assert wf.nodes[up_node_id].class_type == "ResizeImageMaskNode"

    resize_nodes = nodes_by_class_type(wf, "ResizeImageMaskNode")
    for rn in resize_nodes:
        down = l.downstream(rn.id)
        assert len(down) == 1
        down_node_id = next(iter(down))
        assert wf.nodes[down_node_id].class_type == "LTXVImgToVideoConditionOnly"


def test_lens_registered_input_target_on_tiny_workflow() -> None:
    """registered_input_target finds inputs registered by name."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    si = l.registered_input_target("start_image")
    assert si is not None
    assert si.node_id == "1"  # first node created in tiny workflow

    ei = l.registered_input_target("end_image")
    assert ei is not None

    # Missing input
    assert l.registered_input_target("nonexistent") is None


def test_lens_node_value_reads_widgets_and_inputs() -> None:
    """node_value reads from widgets (priority) then inputs."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    assert len(cond_nodes) == 2
    for cn in cond_nodes:
        assert l.node_value(cn.id, "widget_0") == 1.0
        assert l.node_value(cn.id, "widget_1") is False


def test_lens_nodes_by_class_type_on_tiny_workflow() -> None:
    """nodes_by_class_type filters by exact class_type."""
    wf = _tiny_first_last_workflow()

    assert len(nodes_by_class_type(wf, "LoadImage")) == 2
    assert len(nodes_by_class_type(wf, "ResizeImageMaskNode")) == 2
    assert len(nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")) == 2
    assert len(nodes_by_class_type(wf, "SaveImage")) == 0


def test_lens_diagnostics_on_tiny_workflow() -> None:
    """diagnostics produces a readable multi-line summary."""
    wf = _tiny_first_last_workflow()
    diag = diagnostics(wf)

    assert "tiny/first_last_smoke" in diag
    assert "LTXVImgToVideoConditionOnly" in diag
    assert "ResizeImageMaskNode" in diag
    assert "LoadImage" in diag


def test_lens_outputs_on_tiny_workflow() -> None:
    """outputs() returns declared workflow outputs."""
    wf = _tiny_first_last_workflow()
    outs = outputs(wf)
    # No output node class types in this tiny fixture, so no outputs
    assert isinstance(outs, list)


# ── LTX parity template smoke through the lens ───────────────────────────


@pytest.mark.xfail(strict=True, reason="Phase 1: LTX parity template missing seed_first/seed_last/frames/fps registrations; LTX family fix required")
def test_lens_ltx_parity_registered_inputs_via_lens() -> None:
    """All named LTX parity inputs are discoverable through the lens
    without reaching for compiled Comfy API JSON."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    required = {
        "first_image": ("1", "image"),
        "last_image": ("2", "image"),
        "prompt": ("130", "text"),
        "negative_prompt": ("127", "text"),
        "seed": ("99", "noise_seed"),
        "seed_first": ("99", "noise_seed"),
        "seed_last": ("99", "noise_seed"),
        "width": ("113", "value"),
        "height": ("98", "value"),
        "frames": ("102", "value"),
        "fps": ("123", "value"),
        "fps_int": ("114", "value"),
        "first_strength": ("136", "strength"),
        "last_strength": ("137", "strength"),
        "model": ("125", "ckpt_name"),
    }
    for name, (node_id, field) in required.items():
        inp = l.registered_input_target(name)
        assert inp is not None, f"missing registered input: {name}"
        assert (inp.node_id, inp.field) == (node_id, field)
    assert l.registered_input_target("vae") is None


def test_lens_ltx_parity_first_last_conditioning_via_lens() -> None:
    """First and last-frame conditioning nodes exist and receive image feeds,
    verified entirely through the lens without compiled link assertions."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    # Portable parity uses the official Lightricks first/last spine that has
    # passed live on 4090: two LTXVAddGuide nodes and direct checkpoint model.
    cond_nodes = nodes_by_class_type(wf, "LTXVAddGuide")
    cond_by_id = {n.id: n for n in cond_nodes}
    assert "136" in cond_by_id, "first-frame guide node missing"
    assert "137" in cond_by_id, "last-frame guide node missing"
    first_node = l.node("136")
    assert first_node is not None
    assert first_node.class_type == "LTXVAddGuide"

    # First frame: node 115 receives image from upstream
    src_stage1 = l.edge_source("136", "image")
    assert src_stage1 is not None, "first latent replacement node has no image feed"
    upstream_stage1 = wf.nodes[src_stage1.from_node]
    assert upstream_stage1.class_type == "LTXVPreprocess", (
        f"first latent replacement image should come from LTXVPreprocess, got {upstream_stage1.class_type}"
    )

    # Last frame: node 111 receives image from upstream
    src_stage2 = l.edge_source("137", "image")
    assert src_stage2 is not None, "last guide node has no image feed"
    upstream_stage2 = wf.nodes[src_stage2.from_node]
    assert upstream_stage2.class_type == "LTXVPreprocess", (
        f"last guide image should come from LTXVPreprocess, got {upstream_stage2.class_type}"
    )

    # Verify that first LTXVPreprocess is fed by a ResizeImageMaskNode (124)
    preproc_src = l.edge_source("132", "image")
    assert preproc_src is not None, "LTXVPreprocess has no image feed"
    assert preproc_src.from_node == "128"

    # Verify the last ResizeImageMaskNode (125) is fed by LoadImage (39, last_image)
    resize_src = l.edge_source("129", "input")
    assert resize_src is not None
    assert resize_src.from_node == "2"


def test_lens_ltx_parity_prompt_negative_paths_via_lens() -> None:
    """Prompt and negative CLIPTextEncode nodes exist with correct text content,
    verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    # Prompt node 128
    prompt_val = l.node_value("130", "text")
    assert isinstance(prompt_val, str) and len(prompt_val) > 0

    # Negative node 112
    neg_val = l.node_value("127", "text")
    assert isinstance(neg_val, str) and len(neg_val) > 0

    # Both are fed by an LTXAVTextEncoderLoader (103)
    for nid in ("130", "127"):
        src = l.edge_source(nid, "clip")
        assert src is not None, f"{nid} has no clip source"
        assert wf.nodes[src.from_node].class_type == "LTXAVTextEncoderLoader"


def test_lens_ltx_parity_seeds_via_lens() -> None:
    """Seed node (100) is RandomNoise, verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    noise_class = wf.nodes["99"].class_type
    assert noise_class == "RandomNoise"
    assert l.node_value("99", "noise_seed") is not None


def test_lens_ltx_parity_dimensions_frames_fps_via_lens() -> None:
    """Dimensions, frames, and FPS are readable
    through the lens without compiled API checks."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    assert wf.nodes["135"].class_type == "EmptyLTXVLatentVideo"
    width = l.node_value("113", "value")
    height = l.node_value("98", "value")
    assert isinstance(width, int) and width > 0
    assert isinstance(height, int) and height > 0

    # frames → PrimitiveInt 102
    assert wf.nodes["102"].class_type == "PrimitiveInt"
    frames = l.node_value("102", "value")
    assert isinstance(frames, int) and frames > 0

    # fps → PrimitiveFloat 123
    assert wf.nodes["123"].class_type == "PrimitiveFloat"
    fps = l.node_value("123", "value")
    assert isinstance(fps, (int, float)) and fps > 0


def test_lens_ltx_parity_distilled_guide_spine_via_lens() -> None:
    """Distilled LTX first/last must use the dedicated checkpoint and Wan2GP guide order."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    assert l.node_value("125", "ckpt_name") == "ltx-2.3-22b-distilled-fp8.safetensors"
    assert l.node("136").class_type == "LTXVAddGuide"
    assert l.node("137").class_type == "LTXVAddGuide"
    assert l.edge_source("136", "latent").node_id == "135"
    assert l.edge_source("137", "latent").node_id == "136"
    assert l.node("2291") is None
    assert l.edge_source("138", "model").node_id == "125"
    assert l.node("2292") is None
    assert l.edge_source("138", "positive").node_id == "137"
    assert l.edge_source("138", "negative").node_id == "137"


def test_lens_ltx_parity_sigmas_via_lens() -> None:
    """ManualSigmas (118) carries the distilled sigma string,
    verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    assert wf.nodes["116"].class_type == "ManualSigmas"
    sigmas = l.node_value("116", "sigmas")
    assert sigmas == "1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0", (
        f"sigmas drifted: {sigmas!r}"
    )


def test_lens_ltx_parity_strength_defaults_via_lens() -> None:
    """First/last frame strength defaults are 1.0, verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    assert l.node_value("136", "strength") == 1.0, "first_frame_strength default != 1.0"
    assert l.node_value("137", "strength") == 1.0, "last_frame_strength default != 1.0"


def test_lens_ltx_parity_custom_nodes_via_lens() -> None:
    """Declared custom nodes match expectations, verified through requirements
    metadata (reachable through the workflow, not compiled JSON)."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")

    assert "ComfyUI-LTXVideo" in wf.requirements.custom_nodes
    assert "rgthree-comfy" not in wf.requirements.custom_nodes


def test_lens_ltx_parity_no_runexx_only_packs_via_lens() -> None:
    """Runexx-only node types are absent from the parity template,
    verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")

    forbidden = {
        "LTXICLoRALoaderModelOnly",
        "LTXAddVideoICLoRAGuide",
        "LTX2SamplingPreviewOverride",
    }
    found = forbidden & {n.class_type for n in wf.nodes.values()}
    assert found == set(), f"Runexx-only nodes leaked into parity template: {found}"


def test_lens_ltx_parity_video_output_via_lens() -> None:
    """SaveVideo output materialization is discoverable through the lens
    without compiled API output index checks."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    outs = l.outputs()
    save_video_outs = [o for o in outs if o.output_type == "SaveVideo"]
    assert len(save_video_outs) >= 1, "no SaveVideo output materialization found"

    # The SaveVideo node should be downstream of something
    for svo in save_video_outs:
        up = l.upstream(svo.node_id)
        assert len(up) > 0, f"SaveVideo {svo.node_id} is disconnected"


def test_lens_ltx_parity_source_is_pure_python() -> None:
    """The parity template is a manual ready Python template, not a JSON
    wrapper."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")

    assert wf.metadata["source_role"] == "materialized_ready_python_template"
    assert wf.metadata.get("coverage_tier") in {None, "supplemental", "required"}


def test_lens_ltx_parity_diagnostics_produces_readable_summary() -> None:
    """diagnostics on the real parity template produces a useful human-readable
    summary with node count, inputs, and outputs."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    diag = diagnostics(wf)

    assert "video/ltx2_3_lightricks_first_last_parity" in diag
    assert "LTXVAddGuide" in diag
    assert "SaveVideo" in diag
    assert "inputs (" in diag
