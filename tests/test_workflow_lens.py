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


def test_lens_ltx_parity_registered_inputs_via_lens() -> None:
    """The template exposes five authored controls, model binding, and image alias."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)
    required = {
        "image": ("1", "image"),
        "seed": ("3", "noise_seed"),
        "frames": ("18", "length"),
        "fps": ("28", "fps"),
        "prompt": ("13", "text"),
        "model": ("4", "ckpt_name"),
    }
    # Model discovery adds the retained loader binding to the five authored
    # controls; the image alias resolves to the same declared field.
    assert set(wf.inputs) == {"image", "input_image", "seed", "frames", "fps", "prompt", "model"}
    for name, (node_id, field) in required.items():
        inp = l.registered_input_target(name)
        assert inp is not None, f"missing registered input: {name}"
        assert (inp.node_id, inp.field) == (node_id, field)
    image = l.registered_input_target("image")
    alias = l.registered_input_target("input_image")
    assert image is not None and alias is not None
    assert (alias.node_id, alias.field) == (image.node_id, image.field)


def test_lens_ltx_parity_first_last_conditioning_via_lens() -> None:
    """Both authored guide chains retain their image and latent links."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)
    assert {n.id for n in nodes_by_class_type(wf, "LTXVAddGuide")} == {"19", "20"}
    for node_id in ("14", "15"):
        assert l.node(node_id).class_type == "LTXVPreprocess"
    for node_id in ("1", "2"):
        assert l.node(node_id).class_type == "LoadImage"
    assert l.edge_source("19", "image").from_node == "15"
    assert l.edge_source("20", "image").from_node == "14"
    assert l.edge_source("19", "latent").from_node == "18"
    assert l.edge_source("20", "latent").from_node == "19"
    assert l.edge_source("15", "image").from_node == "11"
    assert l.edge_source("14", "image").from_node == "12"
    assert l.edge_source("11", "input").from_node == "1"
    assert l.edge_source("12", "input").from_node == "2"


def test_lens_ltx_parity_prompt_negative_paths_via_lens() -> None:
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)
    assert isinstance(l.node_value("13", "text"), str) and l.node_value("13", "text")
    assert isinstance(l.node_value("10", "text"), str) and l.node_value("10", "text")
    assert l.node("4").class_type == "LTXAVTextEncoderLoader"
    assert l.edge_source("13", "clip").from_node == "4"
    assert l.edge_source("10", "clip").from_node == "4"


def test_lens_ltx_parity_seeds_via_lens() -> None:
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)
    assert wf.nodes["3"].class_type == "RandomNoise"
    assert l.node_value("3", "noise_seed") == 42


def test_lens_ltx_parity_dimensions_frames_fps_via_lens() -> None:
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)
    assert wf.nodes["11"].class_type == "ResizeImageMaskNode"
    assert wf.nodes["12"].class_type == "ResizeImageMaskNode"
    for node_id in ("11", "12"):
        assert l.node_value(node_id, "resize_type.width") == 832
        assert l.node_value(node_id, "resize_type.height") == 480
    assert wf.nodes["17"].class_type == "GetImageSize"
    assert wf.nodes["18"].class_type == "EmptyLTXVLatentVideo"
    assert l.node_value("18", "length") == 81
    assert wf.nodes["28"].class_type == "CreateVideo"
    assert l.node_value("28", "fps") == 16.0


def test_lens_ltx_parity_distilled_guide_spine_via_lens() -> None:
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)
    assert l.node_value("8", "ckpt_name") == "ltx-2.3-22b-distilled-fp8.safetensors"
    assert l.node("19").class_type == "LTXVAddGuide"
    assert l.node("20").class_type == "LTXVAddGuide"
    assert l.edge_source("19", "latent").node_id == "18"
    assert l.edge_source("20", "latent").node_id == "19"
    assert l.edge_source("21", "model").node_id == "8"
    assert l.edge_source("21", "positive").node_id == "20"
    assert l.edge_source("21", "negative").node_id == "20"


def test_lens_ltx_parity_sigmas_via_lens() -> None:
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)
    assert wf.nodes["6"].class_type == "ManualSigmas"
    assert l.node_value("6", "sigmas") == "1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"


def test_lens_ltx_parity_strength_defaults_via_lens() -> None:
    """Strength is omitted by authored source; lens reflects later edits."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)
    assert l.node_value("19", "strength") is None
    assert l.node_value("20", "strength") is None
    wf.nodes["19"].inputs["strength"] = 0.25
    wf.nodes["20"].inputs["strength"] = 0.75
    assert l.node_value("19", "strength") == 0.25
    assert l.node_value("20", "strength") == 0.75


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
