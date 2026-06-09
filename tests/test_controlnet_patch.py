from __future__ import annotations

from inspect import signature

from vibecomfy.patches.controlnet import applies_to, apply, controlnet_patch, patch
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _empty_workflow() -> VibeWorkflow:
    return VibeWorkflow("cn-test", WorkflowSource("cn-test"))


def _minimal_t2i_workflow() -> VibeWorkflow:
    workflow = _empty_workflow()
    workflow.nodes["text"] = VibeNode("text", "CLIPTextEncode", inputs={"text": "hi"})
    workflow.nodes["sampler"] = VibeNode("sampler", "KSampler", inputs={"seed": 0, "steps": 4})
    workflow.connect("text.0", "sampler.positive")
    return workflow


def _minimal_t2i_with_negative_workflow() -> VibeWorkflow:
    workflow = _empty_workflow()
    workflow.nodes["text_pos"] = VibeNode("text_pos", "CLIPTextEncode", inputs={"text": "hi"})
    workflow.nodes["text_neg"] = VibeNode("text_neg", "CLIPTextEncode", inputs={"text": "low quality"})
    workflow.nodes["sampler"] = VibeNode("sampler", "KSampler", inputs={"seed": 0, "steps": 4})
    workflow.connect("text_pos.0", "sampler.positive")
    workflow.connect("text_neg.0", "sampler.negative")
    return workflow


def test_applies_to_returns_false_on_empty_workflow() -> None:
    workflow = _empty_workflow()
    assert applies_to(workflow) is False


def test_applies_to_returns_true_on_workflow_with_ksampler_positive_edge() -> None:
    workflow = _minimal_t2i_workflow()
    assert applies_to(workflow) is True


def test_apply_splices_controlnet_into_positive_chain() -> None:
    workflow = _minimal_t2i_workflow()
    apply(workflow)

    # Original CLIPTextEncode node still present.
    assert "text" in workflow.nodes
    assert workflow.nodes["text"].class_type == "CLIPTextEncode"

    # New ControlNet nodes added.
    class_types = [node.class_type for node in workflow.nodes.values()]
    assert class_types.count("ControlNetLoader") == 1
    assert class_types.count("ControlNetApplyAdvanced") == 1

    loader_id = next(nid for nid, n in workflow.nodes.items() if n.class_type == "ControlNetLoader")
    apply_id = next(nid for nid, n in workflow.nodes.items() if n.class_type == "ControlNetApplyAdvanced")

    api = workflow.compile()

    # ControlNetApply receives the original positive source.
    assert api[apply_id]["inputs"]["positive"] == ["text", 0]
    # ControlNetLoader feeds the apply node's control_net input.
    assert api[apply_id]["inputs"]["control_net"] == [loader_id, 0]
    # KSampler now reads positive conditioning from the apply node.
    assert api["sampler"]["inputs"]["positive"] == [apply_id, 0]


def test_apply_adds_controlnet_custom_node_pack() -> None:
    workflow = _minimal_t2i_workflow()
    apply(workflow)
    assert "ComfyUI-ControlNet" in workflow.requirements.custom_nodes
    # Idempotent: re-applying does not double-register.
    apply(workflow)
    assert workflow.requirements.custom_nodes.count("ComfyUI-ControlNet") == 1


def test_registered_controlnet_patch_uses_standard_apply_contract() -> None:
    assert list(signature(apply).parameters) == ["workflow"]
    assert list(signature(patch.apply).parameters) == ["workflow"]


def test_controlnet_patch_factory_captures_configuration() -> None:
    workflow = _minimal_t2i_workflow()

    configured = controlnet_patch(control_net_name="canny.safetensors", strength=0.5)
    configured.apply(workflow)

    loader = next(node for node in workflow.nodes.values() if node.class_type == "ControlNetLoader")
    apply_node = next(node for node in workflow.nodes.values() if node.class_type == "ControlNetApplyAdvanced")
    assert loader.widgets["control_net_name"] == "canny.safetensors"
    assert apply_node.widgets["strength"] == 0.5


def test_registered_controlnet_patch_records_deterministic_topology_telemetry() -> None:
    workflow = _minimal_t2i_with_negative_workflow()

    patch.apply(workflow)

    telemetry = workflow.metadata["patch_applications"]
    assert len(telemetry) == 1
    assert telemetry[0]["name"] == "controlnet"
    assert telemetry[0]["called"] is True
    assert telemetry[0]["topology_changed"] is True
    assert [item["class_type"] for item in telemetry[0]["nodes_added"]] == [
        "ControlNetLoader",
        "ControlNetApplyAdvanced",
        "ControlNetApplyAdvanced",
    ]
    assert {(item["to_node"], item["to_input"]) for item in telemetry[0]["rewritten_edges"]} == {
        ("sampler", "positive"),
        ("sampler", "negative"),
    }
    assert all(
        item["previous_from_node"] in {"text_pos", "text_neg"} and item["new_from_node"].isdigit()
        for item in telemetry[0]["rewritten_edges"]
    )


def test_registered_controlnet_patch_records_noop_telemetry_without_positive_chain() -> None:
    workflow = _empty_workflow()
    workflow.nodes["sampler"] = VibeNode("sampler", "KSampler", inputs={"seed": 0, "steps": 4})

    patch.apply(workflow)

    assert [node.class_type for node in workflow.nodes.values()] == ["KSampler"]
    assert workflow.metadata["patch_applications"] == [
        {
            "name": "controlnet",
            "layer": "patch",
            "called": True,
            "topology_changed": False,
            "nodes_added": [],
            "introduced_edges": [],
            "rewritten_edges": [],
        }
    ]
