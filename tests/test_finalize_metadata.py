from __future__ import annotations

from dataclasses import asdict, replace

from vibecomfy.blocks.save import image as save_image
from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.registry.ready_template import bind_input
from vibecomfy.workflow import VibeInput, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource


def test_finalize_metadata_matches_convert_to_vibe_format_for_equivalent_graph() -> None:
    workflow = VibeWorkflow("metadata", WorkflowSource("metadata"))
    text = workflow.add_node("CLIPTextEncode", text="hello")
    save = workflow.add_node("SaveVideo", video="placeholder")
    workflow.connect(f"{text.id}.0", f"{save.id}.video")
    workflow.finalize_metadata()

    converted = convert_to_vibe_format(
        {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "hello"}},
            "2": {"class_type": "SaveVideo", "inputs": {"video": ["1", 0]}},
        },
        workflow_id="metadata",
    )

    assert workflow.inputs == converted.inputs
    assert workflow.outputs == converted.outputs
    assert workflow.requirements == converted.requirements


def test_save_video_registers_output() -> None:
    workflow = VibeWorkflow("video-output", WorkflowSource("video-output"))
    workflow.add_node("SaveVideo", video="placeholder")
    workflow.finalize_metadata()

    assert workflow.outputs == [VibeOutput(node_id="1", output_type="SaveVideo")]


def test_finalize_metadata_orders_outputs_by_numeric_node_id() -> None:
    workflow = VibeWorkflow("ordered-output", WorkflowSource("ordered-output"))
    # After T12, _next_node_id returns lowest unused positive int.
    # First add_node gets "1"; we rename it to "12" via direct nodes manipulation.
    # Second add_node now sees gap at "1" and allocates "1"; we rename it to "5".
    first = workflow.add_node("SaveVideo", video="placeholder")
    first.id = "12"
    workflow.nodes["12"] = workflow.nodes.pop("1")
    second = workflow.add_node("SaveVideo", video="placeholder")
    second.id = "5"
    allocated_key = next(k for k in workflow.nodes if k != "12")
    workflow.nodes["5"] = workflow.nodes.pop(allocated_key)
    workflow.finalize_metadata()

    assert [output.node_id for output in workflow.outputs] == ["5", "12"]


def test_finalize_metadata_preserves_bind_input_registered_inputs() -> None:
    workflow = VibeWorkflow("regression", WorkflowSource("regression"))
    workflow.add_node("LoadImage", image="placeholder")
    workflow.add_node("SaveImage", filename_prefix="out/regression")
    workflow.connect("1.0", "2.images")

    bind_input(workflow, "prefix", "2", "filename_prefix")
    assert "prefix" in workflow.inputs

    workflow.finalize_metadata()

    assert workflow.inputs["prefix"].node_id == "2"
    assert workflow.inputs["prefix"].field == "filename_prefix"
    assert tuple(workflow.inputs) == ("prefix",)


def test_finalize_metadata_preserves_manual_input_descriptor_metadata() -> None:
    workflow = VibeWorkflow("manual", WorkflowSource("manual"))
    workflow.add_node("SaveImage", filename_prefix="old")
    workflow.register_input(
        "prefix",
        "1",
        "filename_prefix",
        "old",
        type="STRING",
        default="default-prefix",
        required=True,
        range=("a", "z"),
        aliases=["filename_prefix", "out_prefix"],
        media_semantics="image",
    )

    workflow.finalize_metadata()

    assert workflow.inputs["prefix"] == VibeInput(
        name="prefix",
        node_id="1",
        field="filename_prefix",
        value="old",
        type="STRING",
        default="default-prefix",
        required=True,
        range=("a", "z"),
        aliases=("filename_prefix", "out_prefix"),
        media_semantics="image",
    )


def test_finalize_metadata_is_idempotent_for_manual_and_inferred_inputs() -> None:
    workflow = VibeWorkflow("manual-idempotent", WorkflowSource("manual-idempotent"))
    workflow.add_node("CLIPTextEncode", text="hello")
    workflow.add_node("SaveImage", filename_prefix="first")
    workflow.register_input(
        "prefix",
        "2",
        "filename_prefix",
        "first",
        type="STRING",
        default="default-prefix",
        required=True,
        aliases=["out_prefix"],
        media_semantics="image",
    )

    workflow.finalize_metadata()
    first_inputs = {name: replace(vibe_input) for name, vibe_input in workflow.inputs.items()}
    first_outputs = list(workflow.outputs)
    first_requirements = workflow.requirements

    workflow.finalize_metadata()

    assert workflow.inputs == first_inputs
    assert workflow.outputs == first_outputs
    assert workflow.requirements == first_requirements


def test_finalize_metadata_manual_input_precedes_inferred_collision() -> None:
    workflow = VibeWorkflow("manual-collision", WorkflowSource("manual-collision"))
    workflow.add_node("CLIPTextEncode", text="inferred prompt")
    workflow.add_node("CustomPromptNode", prompt="manual prompt")
    workflow.register_input(
        "prompt",
        "2",
        "prompt",
        "manual prompt",
        type="STRING",
        default="manual default",
        aliases=["caption"],
    )

    workflow.finalize_metadata()

    assert workflow.inputs["prompt"].node_id == "2"
    assert workflow.inputs["prompt"].field == "prompt"
    assert workflow.inputs["prompt"].aliases == ("caption",)
    assert workflow.inputs["prompt"].default == "manual default"


def test_finalize_metadata_preserves_mixed_inferred_and_manual_inputs() -> None:
    workflow = VibeWorkflow("mixed-inputs", WorkflowSource("mixed-inputs"))
    workflow.add_node("CLIPTextEncode", text="manual prompt")
    workflow.add_node("EmptyLatentImage", width=640, height=360)
    workflow.register_input(
        "ratio",
        "2",
        "width",
        640,
        type="INT",
        default=640,
        required=True,
        aliases=["canvas_width"],
    )

    workflow.finalize_metadata()

    assert tuple(workflow.inputs) == ("prompt", "ratio")
    assert workflow.inputs["prompt"].field == "text"
    assert workflow.inputs["ratio"] == VibeInput(
        name="ratio",
        node_id="2",
        field="width",
        value=640,
        type="INT",
        default=640,
        required=True,
        range=None,
        aliases=("canvas_width",),
        media_semantics=None,
    )
def test_finalize_metadata_drops_manual_input_with_missing_node() -> None:
    workflow = VibeWorkflow("manual-missing-node", WorkflowSource("manual-missing-node"))
    workflow.add_node("SaveImage", filename_prefix="old")
    workflow.register_input("prefix", "1", "filename_prefix", "old")
    workflow.nodes.pop("1")

    workflow.finalize_metadata()

    assert "prefix" not in workflow.inputs


def test_finalize_metadata_drops_manual_input_with_missing_field() -> None:
    workflow = VibeWorkflow("manual-missing-field", WorkflowSource("manual-missing-field"))
    workflow.add_node("SaveImage", filename_prefix="old")
    workflow.register_input("prefix", "1", "filename_prefix", "old")
    workflow.nodes["1"].inputs.pop("filename_prefix")

    workflow.finalize_metadata()

    assert "prefix" not in workflow.inputs


def test_finalize_metadata_drops_manual_input_after_target_replacement() -> None:
    workflow = VibeWorkflow("manual-replaced-node", WorkflowSource("manual-replaced-node"))
    workflow.add_node("SaveImage", filename_prefix="old")
    workflow.register_input("prefix", "1", "filename_prefix", "old")
    workflow.nodes["1"].inputs = {"images": "placeholder"}

    workflow.finalize_metadata()

    assert "prefix" not in workflow.inputs


def test_finalize_metadata_allows_post_finalize_manual_registration_and_later_preservation() -> None:
    workflow = VibeWorkflow("post-finalize-register", WorkflowSource("post-finalize-register"))
    workflow.add_node("CLIPTextEncode", text="hello")
    workflow.add_node("SaveImage", filename_prefix="initial")

    workflow.finalize_metadata()
    workflow.register_input(
        "prefix",
        "2",
        "filename_prefix",
        "initial",
        aliases=["out_prefix"],
        media_semantics="image",
    )

    assert workflow.inputs["prefix"].aliases == ("out_prefix",)

    workflow.finalize_metadata()

    assert tuple(workflow.inputs) == ("prompt", "prefix")
    assert workflow.inputs["prefix"] == VibeInput(
        name="prefix",
        node_id="2",
        field="filename_prefix",
        value="initial",
        type=None,
        default="initial",
        required=False,
        range=None,
        aliases=("out_prefix",),
        media_semantics="image",
    )


def test_finalize_metadata_keeps_exec_semantic_io_names_out_of_public_inputs() -> None:
    workflow = VibeWorkflow("exec-metadata", WorkflowSource("exec-metadata"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.exec",
        inputs={"in_0": ["2", 0]},
        widgets={
            "source": "return {'image': image}",
            "io": {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]},
        },
    )
    workflow.nodes["2"] = VibeNode("2", "LoadImage", inputs={"image": "input.png"})

    workflow.finalize_metadata()
    compiled = workflow.compile("api")

    assert tuple(workflow.inputs) == ()
    assert compiled["1"]["inputs"]["in_0"] == ["2", 0]
    assert compiled["1"]["inputs"]["source"] == "return {'image': image}"
    assert compiled["1"]["inputs"]["io"] == {
        "inputs": [["image", "IMAGE"]],
        "outputs": [["image", "IMAGE"]],
    }


def test_finalize_trap_pre_vs_post_requirements_models_nonempty() -> None:
    """Prove the #12 trap: pre-finalize requirements.models is empty;
    post-finalize it is non-empty and runtime-serializable via asdict."""
    workflow = VibeWorkflow(
        "m3-save-node-finalize",
        WorkflowSource("m3-save-node-finalize"),
    )
    workflow.add_node(
        "CheckpointLoaderSimple", ckpt_name="sd_xl_base_1.0.safetensors"
    )
    source = workflow.add_node("LoadImage", image="input/source.png")
    save_image(
        workflow, images=f"{source.id}.0", filename_prefix="m3/finalized"
    )

    # Pre-finalize: requirements.models should be empty (the trap).
    assert workflow.requirements.models == [], (
        "pre-finalize requirements.models must be empty"
    )

    workflow.finalize_metadata()

    # Post-finalize: requirements.models must be non-empty.
    assert len(workflow.requirements.models) > 0, (
        "post-finalize requirements.models must be non-empty"
    )

    # Prove runtime-serializable: asdict produces a plain dict with
    # JSON-safe values (no raw dataclass instances).
    serialized = asdict(workflow.requirements)
    assert isinstance(serialized, dict)
    assert isinstance(serialized.get("models"), list)
    assert len(serialized["models"]) > 0
    assert all(isinstance(m, str) for m in serialized["models"])
