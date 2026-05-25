from __future__ import annotations

import inspect
import tomllib
from pathlib import Path

import pytest

from vibecomfy.nodes.core import EmptyImage, SaveImage
from vibecomfy.templates import new_workflow
from vibecomfy.workflow_context import unbind_workflow


def test_generated_wrapper_uses_context_workflow_and_preserves_source_id() -> None:
    wf = new_workflow({"ready_template": "image/example"}, source_path="ready_templates/image/example.py")

    with wf:
        image = EmptyImage(_id="7", width=64, height=64)

    assert image.node.id == "7"
    assert wf.nodes["7"].class_type == "EmptyImage"
    assert wf.nodes["7"].inputs["width"] == 64
    assert wf.metadata["id_map"]["7"] == "7"


def test_generated_wrapper_accepts_explicit_workflow_outside_context() -> None:
    wf = new_workflow({"ready_template": "image/example"}, source_path="ready_templates/image/example.py")

    image = EmptyImage(wf, _id="8", width=32, height=32)

    assert image.node.id == "8"
    assert wf.nodes["8"].class_type == "EmptyImage"
    assert wf.nodes["8"].inputs["height"] == 32


def test_generated_wrapper_rejects_multiple_positional_workflows() -> None:
    first = new_workflow({"ready_template": "image/first"}, source_path="ready_templates/image/first.py")
    # new_workflow eagerly binds (SD3); release before creating a second so the
    # nested-context guard does not fire. This test exercises wrapper positional
    # arg handling, not the context lifecycle.
    unbind_workflow(first)
    second = new_workflow({"ready_template": "image/second"}, source_path="ready_templates/image/second.py")

    with pytest.raises(TypeError, match="EmptyImage\\(\\) takes at most 1 positional argument, got 2"):
        EmptyImage(first, second, width=16, height=16)


def test_generated_wrapper_requires_context_when_workflow_omitted() -> None:
    with pytest.raises(RuntimeError, match="No active workflow"):
        EmptyImage(width=16, height=16)


def test_generated_wrapper_preserves_extras_and_pass_raw() -> None:
    wf = new_workflow({"ready_template": "image/example"}, source_path="ready_templates/image/example.py")

    image = EmptyImage(wf, _id="9", width=16, height=16)
    saved = SaveImage(wf, _id="10", images=image, filename_prefix="out", custom_extra="kept", pass_raw=True)

    assert saved.node.id == "10"
    assert wf.nodes["10"].inputs["custom_extra"] == "kept"
    assert wf.nodes["10"].inputs["images"] is image


def test_generated_wrapper_annotations_use_literal_and_omitted_sentinel() -> None:
    from vibecomfy.nodes.core import KSampler

    signature = inspect.signature(KSampler)
    sampler_annotation = signature.parameters["sampler_name"].annotation
    steps_annotation = signature.parameters["steps"].annotation

    assert "Literal[" in sampler_annotation
    assert "Any" not in sampler_annotation
    assert "_Omitted" in sampler_annotation
    assert steps_annotation == "int | _Omitted"


def test_generated_stubs_and_typed_marker_are_present() -> None:
    root = Path(__file__).resolve().parents[1]
    core_stub = root / "vibecomfy" / "nodes" / "_generated" / "core.pyi"
    core_reexport_stub = root / "vibecomfy" / "nodes" / "core.pyi"
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    artifacts = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["artifacts"]

    assert (root / "vibecomfy" / "py.typed").is_file()
    assert "vibecomfy/py.typed" in artifacts
    assert "vibecomfy/**/*.pyi" in artifacts
    text = core_stub.read_text(encoding="utf-8")
    assert "def KSampler(" in text
    assert "sampler_name: Literal[" in text
    assert "'euler'" in text
    assert "sampler_name: Literal[" in (root / "vibecomfy" / "nodes" / "_generated" / "core.py").read_text(encoding="utf-8")
    assert "steps: int | _Omitted = ..." in text
    assert "denoise: float | _Omitted = ..." in text
    assert "pass_raw: bool = ..." in text
    assert "**_extras: Any" in text
    assert "| _Omitted = ..." in text
    assert core_reexport_stub.is_file()
    assert "from vibecomfy.nodes._generated.core import *" in core_reexport_stub.read_text(encoding="utf-8")
