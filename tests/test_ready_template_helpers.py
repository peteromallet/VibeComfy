from __future__ import annotations

import pytest

from vibecomfy.errors import SchemaValidationError
from vibecomfy.handles import Handle
from vibecomfy.registry.ready_template import (
    bind_input,
    bind_output,
    finalize_ready_template,
    ready_node,
    ready_workflow,
)
from vibecomfy.workflow import VibeOutput, VibeWorkflow


# ---------------------------------------------------------------------------
# (a) ready_workflow creates VibeWorkflow with correct source/id/source_type/provenance
# ---------------------------------------------------------------------------
def test_ready_workflow_creates_vibe_workflow_with_correct_metadata() -> None:
    wf = ready_workflow(
        "image/sample",
        source_path="/tmp/test_template.py",
        source_type="ready_template",
        provenance={"origin": "unit_test"},
    )

    assert isinstance(wf, VibeWorkflow)
    assert wf.id == "image/sample"
    assert wf.source.id == "image/sample"
    assert wf.source.path == "/tmp/test_template.py"
    assert wf.source.source_type == "ready_template"
    assert wf.source.provenance == {"origin": "unit_test"}


def test_ready_workflow_defaults_provenance_to_empty_dict() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    assert wf.source.provenance == {}


def test_ready_workflow_allows_custom_source_type() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py", source_type="scratchpad")
    assert wf.source.source_type == "scratchpad"


# ---------------------------------------------------------------------------
# (b) ready_node preserves node ids, _extras, output metadata, and compiled
#     links matching old _node helper behavior
# ---------------------------------------------------------------------------
def test_ready_node_preserves_source_id_when_different_from_auto_id() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")

    # Add a node first so auto-id starts at 2 for the next one
    wf.add_node("LoadImage", image="placeholder")

    builder = ready_node(wf, "SaveImage", source_id="20")
    assert builder.node.id == "20"
    assert "20" in wf.nodes
    assert wf.nodes["20"].class_type == "SaveImage"

    # The auto-assigned id (2) should have been replaced
    assert "2" not in wf.nodes


def test_ready_node_does_not_rename_when_source_id_matches() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    builder = ready_node(wf, "LoadImage", source_id="1")
    # auto-id should be "1" for the first node
    assert builder.node.id == "1"
    assert "1" in wf.nodes


def test_ready_node_applies_extras() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    builder = ready_node(
        wf, "SaveImage", source_id="10", extras={"resize_type.multiple": 3}
    )
    assert builder.node.inputs["resize_type.multiple"] == 3


def test_ready_node_extras_handle_connects_edges() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    src = ready_node(wf, "LoadImage", source_id="5")

    builder = ready_node(
        wf, "SaveImage", source_id="10", extras={"images": src.out(0)}
    )
    assert builder.node is not None
    assert any(
        edge.from_node == "5" and edge.to_node == "10" and edge.to_input == "images"
        for edge in wf.edges
    )


def test_ready_node_preserves_output_metadata() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    builder = ready_node(
        wf, "CLIPTextEncode", source_id="3", outputs=("CONDITIONING",)
    )
    assert builder.node.metadata.get("output_names") == ["CONDITIONING"]


def test_ready_node_compiled_links_match_old_helper() -> None:
    """End-to-end: ready_node nodes compile to correct API links."""
    wf = ready_workflow("test", source_path="/tmp/test.py")
    load = ready_node(wf, "LoadImage", source_id="10")
    save = ready_node(
        wf,
        "SaveImage",
        source_id="20",
        extras={"images": load.out(0)},
    )

    api = wf.compile("api")
    assert api["20"]["inputs"]["images"] == ["10", 0]
    assert api["10"]["class_type"] == "LoadImage"


def test_ready_node_renames_edge_references_when_source_id_differs() -> None:
    """Edge references are updated when source_id renames a node."""
    wf = ready_workflow("test", source_path="/tmp/test.py")

    # First add a node to bump the auto-id counter beyond 1
    wf.add_node("PrimitiveInt", value="42")

    # Now add a node that will get auto-id 2, but we want it as source_id="10"
    load = ready_node(wf, "LoadImage", source_id="10")

    # And a save that connects to it
    save = ready_node(
        wf,
        "SaveImage",
        source_id="20",
        extras={"images": load.out(0)},
    )

    # Compile should still work — the edge should reference "10", not "2"
    api = wf.compile("api")
    assert api["20"]["inputs"]["images"] == ["10", 0]


def test_ready_node_source_id_renames_from_edges_too() -> None:
    """When a node is renamed, edges FROM that node also get updated."""
    wf = ready_workflow("test", source_path="/tmp/test.py")

    # Bump counter
    wf.add_node("PrimitiveInt", value="1")
    wf.add_node("PrimitiveInt", value="2")

    # This gets auto-id 3, rename to "30"
    load = ready_node(wf, "LoadImage", source_id="30")
    save = ready_node(
        wf,
        "SaveImage",
        source_id="40",
        extras={"images": load.out(0)},
    )

    api = wf.compile("api")
    assert api["40"]["inputs"]["images"] == ["30", 0]


def test_ready_node_returns_node_builder_with_out_method() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    builder = ready_node(wf, "LoadImage", source_id="1")
    h = builder.out(0)
    assert isinstance(h, Handle)
    assert h.node_id == "1"
    assert h.output_slot == 0


def test_ready_node_named_outputs_via_outputs_metadata() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    builder = ready_node(
        wf, "CLIPTextEncode", source_id="5", outputs=("CONDITIONING",)
    )
    h = builder.out("CONDITIONING")
    assert h.node_id == "5"
    assert h.output_slot == 0  # index of "CONDITIONING" in outputs tuple


def test_ready_node_without_outputs_does_not_set_metadata() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    builder = ready_node(wf, "LoadImage", source_id="1")
    assert "output_names" not in builder.node.metadata


# ---------------------------------------------------------------------------
# (c) finalize_ready_template → bind_input → set_input → compile('api')
#     mutates the compiled API at the bound node field
# ---------------------------------------------------------------------------
def test_lifecycle_finalize_bind_set_compile() -> None:
    """The critical lifecycle gate: bind_input + set_input must survive
    finalize_ready_template and show up in compile('api')."""
    wf = ready_workflow("image/test", source_path="/tmp/test.py")
    ready_node(wf, "LoadImage", source_id="10")
    ready_node(wf, "SaveImage", source_id="20", filename_prefix="out/default")

    # Connect them
    wf.connect("10.0", "20.images")

    # Finalize first (clears inputs/outputs, re-infers)
    finalize_ready_template(
        wf,
        {"ready_template": "image/test", "source_workflow": "test.json"},
        source_path="/tmp/test.py",
    )

    # Now bind a public input AFTER finalize
    bind_input(wf, "filename_prefix", "20", "filename_prefix")

    # Mutate the bound input
    wf.set_input("filename_prefix", "out/custom")

    # Compile and verify the mutated value is at the correct node field
    api = wf.compile("api")
    assert api["20"]["inputs"]["filename_prefix"] == "out/custom"
    assert wf.inputs["filename_prefix"].value == "out/custom"
    assert wf.inputs["filename_prefix"].node_id == "20"
    assert wf.inputs["filename_prefix"].field == "filename_prefix"


def test_lifecycle_set_input_then_compile_for_node_field() -> None:
    """set_input must update both the VibeInput value AND the node's input dict."""
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "LoadImage", source_id="5")
    ready_node(wf, "SaveImage", source_id="10", filename_prefix="out/default")
    wf.connect("5.0", "10.images")

    finalize_ready_template(
        wf,
        {"ready_template": "test"},
        source_path="/tmp/test.py",
    )

    bind_input(wf, "prefix", "10", "filename_prefix")
    wf.set_input("prefix", "my/prefix")

    # The node's own input dict must reflect the change
    assert wf.nodes["10"].inputs["filename_prefix"] == "my/prefix"
    api = wf.compile("api")
    assert api["10"]["inputs"]["filename_prefix"] == "my/prefix"


def test_bind_input_records_descriptor_metadata_and_alias_sets_compiled_field() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="10", filename_prefix="out/default")

    bind_input(
        wf,
        "filename_prefix",
        "10",
        "filename_prefix",
        type="STRING",
        default="out/default",
        required=True,
        aliases=["prefix"],
        media_semantics="image",
    )

    bound = wf.inputs["filename_prefix"]
    assert bound.type == "STRING"
    assert bound.default == "out/default"
    assert bound.value == "out/default"
    assert bound.required is True
    assert bound.aliases == ("prefix",)
    assert bound.media_semantics == "image"

    wf.set_input("prefix", "out/alias")
    assert bound.default == "out/default"
    assert bound.value == "out/alias"
    assert wf.compile("api")["10"]["inputs"]["filename_prefix"] == "out/alias"


# ---------------------------------------------------------------------------
# (d) bind_output produces a semantic output name in workflow.outputs with
#     artifact_kind/mime_type/filename_prefix
# ---------------------------------------------------------------------------
def test_bind_output_appends_new_output() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="42")

    bind_output(
        wf,
        "42",
        output_type="SaveImage",
        name="final_image",
        artifact_kind="image",
        mime_type="image/png",
        filename_prefix="out/final",
        expected_cardinality="one",
    )

    assert len(wf.outputs) == 1
    out = wf.outputs[0]
    assert out.node_id == "42"
    assert out.output_type == "SaveImage"
    assert out.name == "final_image"
    assert out.artifact_kind == "image"
    assert out.mime_type == "image/png"
    assert out.filename_prefix == "out/final"
    assert out.expected_cardinality == "one"


def test_bind_output_updates_existing_output_in_place() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="7")
    # Pre-populate an output
    wf.outputs.append(VibeOutput(node_id="7", output_type="SaveImage"))

    bind_output(wf, "7", name="updated_name", artifact_kind="image")

    assert len(wf.outputs) == 1
    out = wf.outputs[0]
    assert out.node_id == "7"
    assert out.name == "updated_name"
    assert out.artifact_kind == "image"


def test_bind_output_preserves_workflow_outputs_list() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="1")
    ready_node(wf, "SaveVideo", source_id="2")

    bind_output(wf, "1", name="image_out")
    bind_output(wf, "2", name="video_out", artifact_kind="video")

    assert len(wf.outputs) == 2
    assert wf.outputs[0].name == "image_out"
    assert wf.outputs[1].name == "video_out"
    assert wf.outputs[1].artifact_kind == "video"


def test_bind_output_defaults_to_empty_string_output_type() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="1")

    bind_output(wf, "1", name="img")
    assert wf.outputs[0].output_type == ""


def test_bind_output_none_fields_are_not_overridden() -> None:
    """When bind_output is called without optional fields, existing values survive."""
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="3")
    wf.outputs.append(
        VibeOutput(
            node_id="3",
            output_type="SaveImage",
            name="orig_name",
            artifact_kind="image",
            mime_type="image/png",
            filename_prefix="orig_prefix",
            expected_cardinality="one",
        )
    )

    # Call bind_output with only a new name — other fields should persist
    bind_output(wf, "3", name="new_name")
    out = wf.outputs[0]
    assert out.name == "new_name"
    assert out.artifact_kind == "image"  # preserved
    assert out.mime_type == "image/png"  # preserved
    assert out.filename_prefix == "orig_prefix"  # preserved
    assert out.expected_cardinality == "one"  # preserved


def test_bind_output_updates_expected_cardinality() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="3")
    wf.outputs.append(VibeOutput(node_id="3", output_type="SaveImage", expected_cardinality="one"))

    bind_output(wf, "3", expected_cardinality="many")

    assert wf.outputs[0].expected_cardinality == "many"


# ---------------------------------------------------------------------------
# (e) bind_input raises on missing node
# ---------------------------------------------------------------------------
def test_bind_input_raises_value_error_on_missing_node() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")

    with pytest.raises(SchemaValidationError, match="does not exist"):
        bind_input(wf, "prompt", "999", "text")


def test_bind_input_error_message_includes_node_id_and_workflow_id() -> None:
    wf = ready_workflow("my_wf", source_path="/tmp/test.py")

    with pytest.raises(SchemaValidationError) as exc_info:
        bind_input(wf, "my_input", "nonexistent_node", "field")
    msg = str(exc_info.value)
    assert "nonexistent_node" in msg
    assert "my_wf" in msg
    assert "my_input" in msg


# ---------------------------------------------------------------------------
# (f) bind_input raises on missing field
# ---------------------------------------------------------------------------
def test_bind_input_raises_value_error_on_missing_field() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "LoadImage", source_id="10")

    with pytest.raises(SchemaValidationError, match="not found"):
        bind_input(wf, "bad_field", "10", "nonexistent_field")


def test_bind_input_error_message_includes_field_and_class_type() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "LoadImage", source_id="42")

    with pytest.raises(SchemaValidationError) as exc_info:
        bind_input(wf, "inp", "42", "not_a_real_field")
    msg = str(exc_info.value)
    assert "not_a_real_field" in msg
    assert "42" in msg
    assert "LoadImage" in msg


def test_bind_input_validates_against_node_widgets_too() -> None:
    """bind_input must also accept fields that exist in node.widgets."""
    wf = ready_workflow("test", source_path="/tmp/test.py")
    node = wf.add_node("KSampler")
    node.widgets["seed"] = 42

    # Manually set the node ID so the auto-generated ID doesn't matter
    node.id = "99"
    wf.nodes["99"] = node
    if "1" in wf.nodes:
        del wf.nodes["1"]

    # Should NOT raise — "seed" is in node.widgets
    bind_input(wf, "seed_input", "99", "seed")
    assert wf.inputs["seed_input"].node_id == "99"
    assert wf.inputs["seed_input"].field == "seed"


def test_bind_input_validates_against_node_inputs() -> None:
    """bind_input accepts fields in node.inputs."""
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "LoadImage", source_id="1", image="input.png")

    # "image" is a known LoadImage input
    bind_input(wf, "img_input", "1", "image")
    assert wf.inputs["img_input"].node_id == "1"
    assert wf.inputs["img_input"].field == "image"


def test_bind_input_rejects_alias_collision_with_existing_alias() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="1", filename_prefix="one")
    ready_node(wf, "SaveImage", source_id="2", filename_prefix="two")
    bind_input(wf, "first", "1", "filename_prefix", aliases=["prefix"])

    with pytest.raises(SchemaValidationError, match="existing alias"):
        bind_input(wf, "second", "2", "filename_prefix", aliases=["prefix"])


def test_bind_input_rejects_alias_collision_with_primary_name() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="1", filename_prefix="one")
    ready_node(wf, "SaveImage", source_id="2", filename_prefix="two")
    bind_input(wf, "first", "1", "filename_prefix")

    with pytest.raises(SchemaValidationError, match="existing primary input"):
        bind_input(wf, "second", "2", "filename_prefix", aliases=["first"])


def test_bind_input_rejects_primary_collision_with_existing_alias() -> None:
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "SaveImage", source_id="1", filename_prefix="one")
    ready_node(wf, "SaveImage", source_id="2", filename_prefix="two")
    bind_input(wf, "first", "1", "filename_prefix", aliases=["prefix"])

    with pytest.raises(SchemaValidationError, match="existing alias"):
        bind_input(wf, "prefix", "2", "filename_prefix")


# ---------------------------------------------------------------------------
# (g) calling finalize_metadata after bind_input clears the manual binding
#     (regression doc)
# ---------------------------------------------------------------------------
def test_finalize_metadata_after_bind_input_clears_manual_binding() -> None:
    """Documented regression: finalize_metadata clears inputs/outputs completely,
    so any bind_input calls before it are wiped.  This is why bind MUST come
    after finalize_ready_template."""
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "LoadImage", source_id="10")
    ready_node(wf, "SaveImage", source_id="20", filename_prefix="out/default")
    wf.connect("10.0", "20.images")

    # Bind BEFORE finalize
    bind_input(wf, "filename_prefix", "20", "filename_prefix")
    assert "filename_prefix" in wf.inputs  # It's there now

    # finalize_metadata clears inputs
    wf.finalize_metadata()

    # The binding should be gone
    assert "filename_prefix" not in wf.inputs


def test_bind_after_finalize_survives() -> None:
    """The correct order: finalize first, then bind — binding survives."""
    wf = ready_workflow("test", source_path="/tmp/test.py")
    ready_node(wf, "LoadImage", source_id="10")
    ready_node(wf, "SaveImage", source_id="20", filename_prefix="out/default")
    wf.connect("10.0", "20.images")

    # Finalize first
    finalize_ready_template(
        wf,
        {"ready_template": "test"},
        source_path="/tmp/test.py",
    )

    # Bind after finalize
    bind_input(wf, "filename_prefix", "20", "filename_prefix")

    # Binding must survive
    assert "filename_prefix" in wf.inputs
    assert wf.inputs["filename_prefix"].node_id == "20"
