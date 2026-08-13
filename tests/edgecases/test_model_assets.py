from __future__ import annotations

"""Edge case: model asset tracking through conversion.

Verifies that model-like values in workflow inputs are tracked, aliased,
and not silently dropped during conversion.
"""

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def test_model_value_present_in_source_tracked() -> None:
    """Model-like values (safetensors, ckpt) in inputs should not be lost."""
    wf = VibeWorkflow(
        "model-assets-test",
        WorkflowSource("source/model_assets", source_type="api"),
    )
    wf.nodes["1"] = VibeNode(
        "1",
        "CheckpointLoaderSimple",
        inputs={"ckpt_name": "realisticVisionV51.safetensors"},
    )
    wf.nodes["2"] = VibeNode(
        "2",
        "SaveImage",
        inputs={"filename_prefix": "out/model-test"},
    )
    result = port_convert_workflow(wf)

    assert result.validation is not None
    assert result.validation.ok

    # The emitted text should contain the model filename
    assert "realisticVisionV51.safetensors" in result.text or (
        result.validation.source_model_snapshot
        and any(
            "realisticVisionV51" in v
            for v in result.validation.source_model_snapshot.values()
        )
    )


def test_no_false_model_value_detection() -> None:
    """Scalar values that are not model-like should not be flagged."""
    wf = VibeWorkflow(
        "no-model-assets",
        WorkflowSource("source/no_models", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "hello.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/test"})
    result = port_convert_workflow(wf)

    assert result.validation is not None
    assert result.validation.ok
    assert not result.validation.model_value_change
    assert not result.validation.model_value_dropped
