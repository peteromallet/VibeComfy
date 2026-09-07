"""No-GPU structural proof for the pinned H3 canonical fixture."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.security.agent_generated_loader import load_agent_generated_scratchpad
from vibecomfy.workflow import NodeMode


ROOT = Path(__file__).parent
FIXTURE = ROOT / "fixtures" / "h3_canonical.py"
EXPECTATIONS = ROOT / "fixtures" / "h3_role_expectations.json"


def _expectations() -> dict:
    return json.loads(EXPECTATIONS.read_text(encoding="utf-8"))


def _load_fixture():
    return load_agent_generated_scratchpad(FIXTURE)


def _edge_matches(workflow, spec: list[str]) -> bool:
    _, source_type, target_type, target_input = spec
    for edge in workflow.edges:
        source = workflow.nodes.get(str(edge.from_node))
        target = workflow.nodes.get(str(edge.to_node))
        if source is None or target is None:
            continue
        if source.class_type == source_type and target.class_type == target_type and edge.to_input == target_input:
            return True
    return False


def _assert_role_graph(workflow, *, full_ir: bool) -> None:
    expected = _expectations()
    if full_ir:
        assert len(workflow.nodes) == expected["root_nodes"]
        assert len(workflow.edges) == expected["links"]
        modes = [node.mode for node in workflow.nodes.values()]
        assert modes.count(NodeMode.ENABLED) == expected["enabled_nodes"]
        assert modes.count(NodeMode.BYPASSED) == expected["bypassed_nodes"]

    refs = [n for n in workflow.nodes.values() if n.class_type == "MiniMaxH3ReferenceToVideo"]
    assert len(refs) >= 7
    assert sum(n.class_type == "LoadImage" for n in workflow.nodes.values()) >= 2
    assert sum(n.class_type == "VHS_LoadVideoFFmpeg" for n in workflow.nodes.values()) == 1
    assert sum(n.class_type == "MiniMaxH3CropTo32" for n in workflow.nodes.values()) == 1
    assert sum(n.class_type == "MiniMaxH3StartMaskedContext" for n in workflow.nodes.values()) == 1
    assert sum(n.class_type == "MiniMaxH3GeneratedAVMaskedContext" for n in workflow.nodes.values()) >= 5
    assert sum(n.class_type == "BasicGuider" for n in workflow.nodes.values()) >= 7
    assert sum(n.class_type == "SamplerCustomAdvanced" for n in workflow.nodes.values()) >= 7
    assert sum(n.class_type == "VAEDecode" for n in workflow.nodes.values()) >= 7
    assert sum(n.class_type == "VAEDecodeAudio" for n in workflow.nodes.values()) >= 7
    assert sum(n.class_type == "VHS_VideoCombine" for n in workflow.nodes.values()) >= 7

    for spec in expected["role_edge_examples"]:
        assert _edge_matches(workflow, spec), f"missing role edge: {spec}"

    conditioning_edges = [
        edge for edge in workflow.edges
        if _edge_matches_edge(workflow, edge, "MiniMaxH3ReferenceToVideo", "BasicGuider", "conditioning")
    ]
    # The starter reference feeds its dedicated starter guider; seven
    # continuation references feed the ordinary BasicGuider chain.
    assert len(conditioning_edges) == 7
    assert all(edge.from_output == "0" for edge in conditioning_edges)

    generated_edges = [
        edge for edge in workflow.edges
        if _edge_matches_edge(workflow, edge, "SamplerCustomAdvanced", "MiniMaxH3GeneratedAVMaskedContext", "source_latent")
    ]
    assert len(generated_edges) == sum(
        n.class_type == "MiniMaxH3GeneratedAVMaskedContext" for n in workflow.nodes.values()
    )
    assert all(edge.from_output == "0" for edge in generated_edges)
    generated_ids = {
        str(n.id) for n in workflow.nodes.values()
        if n.class_type == "MiniMaxH3GeneratedAVMaskedContext"
    }
    assert {str(edge.to_node) for edge in generated_edges} == generated_ids
    sampler_ids = {
        str(n.id) for n in workflow.nodes.values()
        if n.class_type == "SamplerCustomAdvanced"
    }
    for generated_id in generated_ids:
        latent_edge = next(
            edge for edge in workflow.edges
            if str(edge.to_node) == generated_id and edge.to_input == "latent"
        )
        assert workflow.nodes[str(latent_edge.from_node)].class_type == "MiniMaxH3ReferenceToVideo"
        producer = next(edge for edge in generated_edges if str(edge.to_node) == generated_id)
        consumer = next(
            edge for edge in workflow.edges
            if str(edge.to_node) in sampler_ids
            and edge.to_input == "latent_image"
            and str(edge.from_node) == generated_id
        )
        assert str(producer.from_node) != str(consumer.to_node)
        consumer_guider = next(
            edge for edge in workflow.edges
            if str(edge.to_node) == str(consumer.to_node) and edge.to_input == "guider"
        )
        guider_conditioning = next(
            edge for edge in workflow.edges
            if str(edge.to_node) == str(consumer_guider.from_node)
            and edge.to_input == "conditioning"
        )
        assert str(guider_conditioning.from_node) == str(latent_edge.from_node)
    masked_latent_edges = [
        edge for edge in workflow.edges
        if _edge_matches_edge(workflow, edge, "MiniMaxH3ReferenceToVideo", "MiniMaxH3StartMaskedContext", "latent")
    ]
    assert len(masked_latent_edges) == 1
    assert masked_latent_edges[0].from_output == "1"

    ref_inputs = {
        edge.to_input
        for edge in workflow.edges
        if _edge_matches_edge(workflow, edge, "LoadImage", "MiniMaxH3ReferenceToVideo", edge.to_input)
        and edge.to_input.startswith("ref_images.ref_image_")
    }
    assert {"ref_images.ref_image_0", "ref_images.ref_image_1"} <= ref_inputs
    reference_sources_by_slot = {"ref_images.ref_image_0": set(), "ref_images.ref_image_1": set()}
    for ref in refs:
        ref_image_edges = [
            edge for edge in workflow.edges
            if str(edge.to_node) == str(ref.id)
            and edge.to_input.startswith("ref_images.ref_image_")
        ]
        per_ref = {
            edge.to_input for edge in workflow.edges
            if str(edge.to_node) == str(ref.id)
            and edge.to_input.startswith("ref_images.ref_image_")
        }
        assert {"ref_images.ref_image_0", "ref_images.ref_image_1"} <= per_ref
        assert len({str(edge.from_node) for edge in ref_image_edges}) == 2
        assert all(edge.from_output == "0" for edge in ref_image_edges)
        for edge in ref_image_edges:
            reference_sources_by_slot[edge.to_input].add(str(edge.from_node))
    assert all(len(sources) == 1 for sources in reference_sources_by_slot.values())
    assert reference_sources_by_slot["ref_images.ref_image_0"] != reference_sources_by_slot["ref_images.ref_image_1"]

    controller = next(n for n in workflow.nodes.values() if n.class_type == "MiniMaxH3AVExtensionController")
    assert [controller.widgets.get(f"widget_{i}") for i in range(5)] == expected["controller_widgets"]
    start_mode = next(n for n in workflow.nodes.values() if n.class_type == "MiniMaxH3AVStartModeParam")
    source_audio_mode = next(n for n in workflow.nodes.values() if n.class_type == "MiniMaxH3AVSourceAudioModeParam")
    assert [start_mode.widgets.get("widget_0")] == expected["start_mode_widget"]
    assert [source_audio_mode.widgets.get("widget_0")] == expected["source_audio_mode_widget"]
    start_context = next(n for n in workflow.nodes.values() if n.class_type == "MiniMaxH3StartMaskedContext")
    assert [start_context.widgets.get(f"widget_{i}") for i in range(4)] == expected["start_context_widgets"]
    generated = next(n for n in workflow.nodes.values() if n.class_type == "MiniMaxH3GeneratedAVMaskedContext")
    assert [generated.widgets.get(f"widget_{i}") for i in range(2)] == expected["generated_context_widgets"]
    starter = next(
        n for n in refs
        if "opening clip for a new continuous video" in str(n.widgets.get("widget_0", ""))
    )
    assert list(starter.widgets.values())[-4:] == expected["starter_reference_tail"]
    expression = next(n for n in workflow.nodes.values() if n.class_type == "ComfyMathExpression")
    assert expression.widgets.get("widget_0") == expected["sampling_expression"]


def test_h3_source_provenance_and_full_ir_role_custody() -> None:
    expected = _expectations()
    workflow = _load_fixture()
    assert workflow.metadata.get("h3_source_sha256") == expected["source_sha256"]
    _assert_role_graph(workflow, full_ir=True)


def test_h3_compiled_api_contains_enabled_active_slice_only() -> None:
    workflow = _load_fixture()
    api = workflow.compile("api")
    assert api
    enabled_ids = {str(node.id) for node in workflow.nodes.values() if node.mode is NodeMode.ENABLED}
    assert set(api).issubset(enabled_ids)
    assert any(value["class_type"] == "MiniMaxH3ReferenceToVideo" for value in api.values())
    assert any(value["class_type"] == "MiniMaxH3StreamLiveExtensionAVToVHS" for value in api.values())
    assert any(value["class_type"] == "MiniMaxH3FinalizeVHSOutput" for value in api.values())
    compiled_types = {value["class_type"] for value in api.values()}
    assert "MiniMaxH3StartMaskedContext" in compiled_types
    assert "SamplerCustomAdvanced" in compiled_types
    assert "VAEDecode" in compiled_types
    assert "VAEDecodeAudio" in compiled_types
    assert "MiniMaxH3GeneratedAVMaskedContext" not in compiled_types

    by_type = {}
    for node_id, value in api.items():
        by_type.setdefault(value["class_type"], []).append((node_id, value))

    def one(class_type: str):
        values = by_type[class_type]
        assert len(values) == 1, f"expected one active {class_type}, got {len(values)}"
        return values[0]

    video_id, _ = one("VHS_LoadVideoFFmpeg")
    crop_id, crop = one("MiniMaxH3CropTo32")
    ref_id, ref = one("MiniMaxH3ReferenceToVideo")
    guider_id, guider = one("BasicGuider")
    masked_id, masked = one("MiniMaxH3StartMaskedContext")
    sampler_id, sampler = one("SamplerCustomAdvanced")
    decode_id, decode = one("VAEDecode")
    audio_decode_id, audio_decode = one("VAEDecodeAudio")
    stream_id, stream = one("MiniMaxH3StreamLiveExtensionAVToVHS")
    finalize_id, finalize = one("MiniMaxH3FinalizeVHSOutput")

    assert crop["inputs"]["images"] == [video_id, 0]
    assert masked["inputs"]["source_frames"] == [crop_id, 0]
    assert guider["inputs"]["conditioning"] == [ref_id, 0]
    assert masked["inputs"]["latent"] == [ref_id, 1]
    assert sampler["inputs"]["guider"] == [guider_id, 0]
    assert sampler["inputs"]["latent_image"] == [masked_id, 0]
    assert decode["inputs"]["samples"] == [sampler_id, 0]
    assert audio_decode["inputs"]["samples"] == [sampler_id, 0]
    assert stream["inputs"]["source_frames"] == [crop_id, 0]
    assert stream["inputs"]["extension_1"] == [sampler_id, 0]
    assert finalize["inputs"]["filenames"] == [stream_id, 0]
    ref_image_keys = {key for key in ref["inputs"] if key.startswith("ref_images.")}
    assert ref_image_keys >= {
        "ref_images.ref_image_0", "ref_images.ref_image_1"
    }
    for key in ("ref_images.ref_image_0", "ref_images.ref_image_1"):
        source_id, source_slot = ref["inputs"][key]
        assert source_slot == 0
        assert api[source_id]["class_type"] == "LoadImage"
    _, combine = one("VHS_VideoCombine")
    assert combine["inputs"]["images"] == [decode_id, 0]
    assert combine["inputs"]["audio"] == [audio_decode_id, 0]


@pytest.mark.parametrize("mutation", [
    "drop_reference_image_edge",
    "cross_role_source_frame",
    "conditioning_to_latent",
    "mask_context_bypass",
    "sampling_math_change",
    "mode_change",
    "same_class_stage_swap",
    "wrong_output_port",
    "swapped_reference_sources",
])
def test_h3_role_negative_mutations_are_rejected(mutation: str) -> None:
    workflow = _load_fixture()
    if mutation == "drop_reference_image_edge":
        edge = next(e for e in workflow.edges if _edge_matches_edge(workflow, e, "LoadImage", "MiniMaxH3ReferenceToVideo", "ref_images.ref_image_0"))
        edge.to_input = "ref_images.ref_image_1"
    elif mutation == "cross_role_source_frame":
        edge = next(e for e in workflow.edges if _edge_matches_edge(workflow, e, "VHS_LoadVideoFFmpeg", "MiniMaxH3CropTo32", "images"))
        edge.from_node = next(n.id for n in workflow.nodes.values() if n.class_type == "BasicGuider")
    elif mutation == "conditioning_to_latent":
        edge = next(e for e in workflow.edges if _edge_matches_edge(workflow, e, "MiniMaxH3ReferenceToVideo", "BasicGuider", "conditioning"))
        edge.to_input = "latent_image"
    elif mutation == "mask_context_bypass":
        workflow.edges.pop(next(i for i, e in enumerate(workflow.edges) if _edge_matches_edge(workflow, e, "MiniMaxH3StartMaskedContext", "SamplerCustomAdvanced", "latent_image")))
    elif mutation == "sampling_math_change":
        node = next(n for n in workflow.nodes.values() if n.class_type == "ComfyMathExpression")
        node.widgets["widget_0"] = "0"
    elif mutation == "mode_change":
        node = next(n for n in workflow.nodes.values() if n.class_type == "MiniMaxH3StartMaskedContext")
        node.mode = NodeMode.BYPASSED
    elif mutation == "same_class_stage_swap":
        stage_edges = [
            e for e in workflow.edges
            if _edge_matches_edge(workflow, e, "SamplerCustomAdvanced", "MiniMaxH3GeneratedAVMaskedContext", "source_latent")
        ]
        stage_edges[0].to_node, stage_edges[1].to_node = stage_edges[1].to_node, stage_edges[0].to_node
    elif mutation == "swapped_reference_sources":
        ref = next(n for n in workflow.nodes.values() if n.class_type == "MiniMaxH3ReferenceToVideo")
        slot_zero = next(e for e in workflow.edges if str(e.to_node) == str(ref.id) and e.to_input == "ref_images.ref_image_0")
        slot_one = next(e for e in workflow.edges if str(e.to_node) == str(ref.id) and e.to_input == "ref_images.ref_image_1")
        slot_zero.from_node, slot_one.from_node = slot_one.from_node, slot_zero.from_node
    else:
        edge = next(e for e in workflow.edges if _edge_matches_edge(workflow, e, "MiniMaxH3ReferenceToVideo", "MiniMaxH3StartMaskedContext", "latent"))
        edge.from_output = "0"
    with pytest.raises((AssertionError, ValueError)):
        _assert_role_graph(workflow, full_ir=True)


def _edge_matches_edge(workflow, edge, source_type: str, target_type: str, target_input: str) -> bool:
    source = workflow.nodes.get(str(edge.from_node))
    target = workflow.nodes.get(str(edge.to_node))
    return source is not None and target is not None and source.class_type == source_type and target.class_type == target_type and edge.to_input == target_input
