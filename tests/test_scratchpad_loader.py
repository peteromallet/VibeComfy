from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from vibecomfy.scratchpad_loader import load_scratchpad


def _runtime_errors():
    return importlib.import_module("vibecomfy.errors")


def test_load_scratchpad_returns_workflow(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="SaveImage")
    return workflow
""",
        encoding="utf-8",
    )

    workflow = load_scratchpad(scratchpad, provenance_override="user_confirmed")
    assert workflow.id == "x"
    assert workflow.validate().ok


def test_load_scratchpad_non_workflow_return_is_typed_build_error(tmp_path: Path) -> None:
    errors = _runtime_errors()
    scratchpad = tmp_path / "bad_return.py"
    scratchpad.write_text(
        """
def build():
    return {"not": "a workflow"}
""",
        encoding="utf-8",
    )

    with pytest.raises(errors.WorkflowBuildError) as exc_info:
        load_scratchpad(scratchpad, provenance_override="user_confirmed")

    assert exc_info.value.next_action
    assert "VibeWorkflow" in str(exc_info.value)


def test_load_scratchpad_internal_typeerror_is_not_malformed_return(tmp_path: Path) -> None:
    scratchpad = tmp_path / "internal_typeerror.py"
    scratchpad.write_text(
        """
def build():
    raise TypeError("user code exploded")
""",
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match="user code exploded"):
        load_scratchpad(scratchpad, provenance_override="user_confirmed")
