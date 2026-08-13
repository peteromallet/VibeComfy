from __future__ import annotations

"""Edge case: determinism guarantees.

Verifies that repeated conversions of the same workflow produce
identical outputs (text and API hash).
"""

import hashlib

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _make_deterministic_workflow() -> VibeWorkflow:
    """Create a deterministic workflow for repeated testing."""
    wf = VibeWorkflow(
        "det-test",
        WorkflowSource("source/det_test", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "dog.png"})
    wf.nodes["2"] = VibeNode(
        "2", "CLIPTextEncode", inputs={"text": "a beautiful landscape"}
    )
    wf.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out/det"})
    wf.edges.append(VibeEdge("1", "0", "3", "images"))
    return wf


def test_same_workflow_produces_same_text() -> None:
    """Same workflow converted twice produces byte-identical text."""
    result1 = port_convert_workflow(_make_deterministic_workflow())
    result2 = port_convert_workflow(_make_deterministic_workflow())

    assert result1.text == result2.text, (
        f"Non-deterministic emission:\n---\n{result1.text}\n---\n{result2.text}"
    )


def test_same_workflow_produces_same_api_hash() -> None:
    """Same workflow converted twice produces same canonical API hash."""
    result1 = port_convert_workflow(_make_deterministic_workflow())
    result2 = port_convert_workflow(_make_deterministic_workflow())

    hash1 = hashlib.sha256(result1.text.encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(result2.text.encode("utf-8")).hexdigest()

    assert hash1 == hash2, f"API text hash mismatch: {hash1} != {hash2}"


def test_determinism_across_workflow_instances() -> None:
    """Different VibeWorkflow instances with same content produce identical output."""
    wf1 = _make_deterministic_workflow()
    wf2 = _make_deterministic_workflow()

    # They're different objects but identical content
    assert wf1 is not wf2

    result1 = port_convert_workflow(wf1)
    result2 = port_convert_workflow(wf2)

    assert result1.text == result2.text
