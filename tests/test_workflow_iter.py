from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def test_multi_output_node_builder_iterates_in_declared_schema_order() -> None:
    wf = VibeWorkflow("iter", WorkflowSource("iter"))
    builder = wf.node("WanImageToVideo")
    builder.node.metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]

    handles = list(builder)

    assert [handle.output_slot for handle in handles] == [0, 1, 2]
    # Retained native names own the slots; metadata cannot rename them.
    assert [handle.name for handle in handles] == ["positive", "negative", "latent"]
    assert [str(handle) for handle in handles] == [
        f"{builder.id}.0",
        f"{builder.id}.1",
        f"{builder.id}.2",
    ]


def test_single_output_node_builder_iterates_one_handle() -> None:
    wf = VibeWorkflow("iter", WorkflowSource("iter"))
    builder = wf.node("VAEDecode")
    builder.node.metadata["output_names"] = ["IMAGE"]

    handles = list(builder)

    assert len(handles) == 1
    assert handles[0].output_slot == 0
    assert handles[0].name == "IMAGE"


def test_named_out_still_works_after_iteration() -> None:
    wf = VibeWorkflow("iter", WorkflowSource("iter"))
    builder = wf.node("WanImageToVideo")
    builder.node.metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]

    list(builder)

    assert builder.out("LATENT").output_slot == 2
    assert builder.out("LATENT").name == "LATENT"
