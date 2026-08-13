from __future__ import annotations

"""Edge case: backward compatibility contracts.

Ensures that emitted templates remain loadable/importable across
the supported Python version range and that no breaking API changes
slip through.
"""

import importlib.util
import tempfile
from pathlib import Path

import pytest

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def test_emitted_text_is_valid_python_syntax() -> None:
    """Emitted text must be valid Python syntax (compile succeeds)."""
    wf = VibeWorkflow(
        "syntax-check",
        WorkflowSource("source/syntax_check", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/test"})
    wf.edges.append(VibeEdge("1", "0", "2", "images"))

    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok

    # compile() should not raise SyntaxError
    compile(result.text, "<emitted>", "exec")


def test_emitted_build_function_returns_vibeworkflow() -> None:
    """The build() function in emitted text must return a VibeWorkflow."""
    wf = VibeWorkflow(
        "build-return",
        WorkflowSource("source/build_return", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out/return"})
    wf.edges.append(VibeEdge("1", "0", "2", "images"))

    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok

    # Execute the emitted module and call build()
    with tempfile.TemporaryDirectory(prefix="vibecomfy-bc-") as tmp:
        path = Path(tmp) / "emitted.py"
        path.write_text(result.text, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("vibecomfy_bc_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        build_fn = getattr(module, "build", None)
        assert callable(build_fn), "build() function missing from emitted module"

        emitted_wf = build_fn()
        assert isinstance(emitted_wf, VibeWorkflow), (
            f"build() returned {type(emitted_wf).__name__}, expected VibeWorkflow"
        )


def test_scratchpad_mode_no_ready_metadata_leak() -> None:
    """Scratchpad mode should not leak READY_METADATA into the emitted text."""
    wf = VibeWorkflow(
        "no-leak",
        WorkflowSource("source/no_leak", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})

    result = port_convert_workflow(wf)
    assert "READY_METADATA" not in result.text
    assert result.mode == "scratchpad"
