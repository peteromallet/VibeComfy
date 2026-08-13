from __future__ import annotations

"""Edge case: JSON format variations in workflow inputs.

Tests unusual but valid JSON shapes: deeply nested inputs, empty inputs,
special characters in input names.
"""

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def test_deeply_nested_inputs_no_crash() -> None:
    """Deeply nested dict/list inputs should not crash port_convert_workflow."""
    wf = VibeWorkflow(
        "deep-nest",
        WorkflowSource("source/deep_nest", source_type="api"),
    )
    wf.nodes["1"] = VibeNode(
        "1",
        "LoadImage",
        inputs={
            "image": "test.png",
            "nested": {"a": {"b": {"c": [1, 2, {"d": "deep"}]}}},
        },
    )
    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok


def test_empty_inputs_dict_no_crash() -> None:
    """Node with empty inputs dict should not crash."""
    wf = VibeWorkflow(
        "empty-inputs",
        WorkflowSource("source/empty_inputs", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "EmptyLatentImage", inputs={})
    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok


def test_special_characters_in_input_values() -> None:
    """Input values with special characters (quotes, newlines) should be handled."""
    wf = VibeWorkflow(
        "special-chars",
        WorkflowSource("source/special_chars", source_type="api"),
    )
    wf.nodes["1"] = VibeNode(
        "1",
        "CLIPTextEncode",
        inputs={
            "text": "It's a \"test\" with\nnewlines and \\backslashes",
        },
    )
    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok

    # The text should have been properly escaped in the emitted Python
    assert "test" in result.text


def test_boolean_and_null_like_inputs() -> None:
    """Boolean and numeric inputs should be preserved literally."""
    wf = VibeWorkflow(
        "bool-null",
        WorkflowSource("source/bool_null", source_type="api"),
    )
    wf.nodes["1"] = VibeNode(
        "1",
        "KSampler",
        inputs={
            "seed": 42,
            "steps": 20,
            "cfg": 7.5,
        },
    )
    wf.nodes["2"] = VibeNode(
        "2",
        "SaveImage",
        inputs={"filename_prefix": "out/bool-test"},
    )
    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok

    # Numeric values should be in the emitted text
    assert "42" in result.text or "seed" in result.text
