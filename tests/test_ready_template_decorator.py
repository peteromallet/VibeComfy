"""Tests for the @ready_template decorator and PublicInput.

Covers:
- AST validation at decoration time: typos in PublicInput(node=...) raise.
- Runtime resolution of inputs and output via captured locals.
- Backwards compat: the legacy flat shape (wf = new_workflow + return
  wf.finalize) still works alongside the decorator path.
"""
from __future__ import annotations

import pytest

from vibecomfy.templates import (
    InputSpec,
    PublicInput,
    ReadyMetadata,
    new_workflow,
    ready_template,
)
from vibecomfy.workflow import VibeWorkflow


def _basic_metadata() -> dict:
    return ReadyMetadata.build(
        capability="text_to_image",
        template_id="test/decorator_smoke",
    )


def _build_minimal_save_workflow(wf: VibeWorkflow):
    """Add a trivial CLIPTextEncode + SaveImage subgraph used by the smoke tests."""
    # Use raw add_node to avoid pulling typed wrappers (which need schemas).
    clip_node = wf.add_node("CLIPTextEncode", text="hello")
    save_node = wf.add_node("SaveImage", images=[clip_node.id, 0], filename_prefix="x")
    return clip_node, save_node


def test_decorator_emits_public_inputs_and_output():
    metadata = _basic_metadata()

    @ready_template(
        metadata,
        source_path=__file__,
        inputs={
            "prompt": PublicInput(node="clip_node", field="text", default="hello", type="STRING"),
        },
        output=dict(node="save_node", output_type="SaveImage", name="image",
                    artifact_kind="image", mime_type="image/png"),
    )
    def build():
        clip_node = __wf__.add_node("CLIPTextEncode", text="hello")  # type: ignore[name-defined]  # noqa: F841
        save_node = __wf__.add_node("SaveImage",  # type: ignore[name-defined]  # noqa: F841
                                    images=[clip_node.id, 0], filename_prefix="x")

    # We need the wf available inside build() — patch via globals injection.
    # Simpler approach: define an inner build that uses the active ContextVar.
    @ready_template(
        metadata,
        source_path=__file__,
        inputs={
            "prompt": PublicInput(node="clip_node", field="text", default="hello", type="STRING"),
        },
        output=dict(node="save_node", output_type="SaveImage", name="image",
                    artifact_kind="image", mime_type="image/png"),
    )
    def build2():
        from vibecomfy.workflow_context import active_workflow
        wf = active_workflow()
        clip_node = wf.add_node("CLIPTextEncode", text="hello")
        save_node = wf.add_node("SaveImage", images=[clip_node.id, 0], filename_prefix="x")  # noqa: F841

    finalized = build2()
    assert isinstance(finalized, VibeWorkflow)
    assert "prompt" in finalized.inputs
    assert finalized.inputs["prompt"].field == "text"
    assert finalized.outputs, "expected output bound by finalize()"


def test_decorator_ast_validation_rejects_typo():
    metadata = _basic_metadata()

    with pytest.raises(ValueError, match="do not resolve to locals"):
        @ready_template(
            metadata,
            source_path=__file__,
            inputs={
                "prompt": PublicInput(node="wrong_name", field="text", default="hi"),
            },
        )
        def build():
            from vibecomfy.workflow_context import active_workflow
            wf = active_workflow()
            clip_node = wf.add_node("CLIPTextEncode", text="hi")  # noqa: F841


def test_decorator_ast_validation_rejects_bad_output():
    metadata = _basic_metadata()

    with pytest.raises(ValueError, match="output\\['node'\\]"):
        @ready_template(
            metadata,
            source_path=__file__,
            output=dict(node="missing_save", output_type="SaveImage"),
        )
        def build():
            from vibecomfy.workflow_context import active_workflow
            wf = active_workflow()
            clip = wf.add_node("CLIPTextEncode", text="x")  # noqa: F841


def test_decorator_message_lists_available_locals():
    metadata = _basic_metadata()

    with pytest.raises(ValueError) as exc:
        @ready_template(
            metadata,
            source_path=__file__,
            inputs={"prompt": PublicInput(node="ghost", field="text")},
        )
        def build():
            from vibecomfy.workflow_context import active_workflow
            wf = active_workflow()
            cliptextencode = wf.add_node("CLIPTextEncode", text="x")  # noqa: F841

    msg = str(exc.value)
    assert "ghost" in msg
    assert "Available locals" in msg
    assert "cliptextencode" in msg


def test_decorator_supports_tuple_unpacked_locals():
    metadata = _basic_metadata()

    @ready_template(
        metadata,
        source_path=__file__,
        inputs={"steps": PublicInput(node="sampler", field="steps", default=20, type="INT")},
    )
    def build():
        from vibecomfy.workflow_context import active_workflow
        wf = active_workflow()
        sampler, _other = wf.add_node("KSampler", steps=20), None
        return sampler

    # AST check should accept tuple assignment targets.
    # Runtime path may fail because KSampler needs schema; we only check decoration.
    assert getattr(build, "_vibecomfy_ready_template", False) is True


def test_legacy_flat_shape_still_works():
    """The pre-existing wf = new_workflow + wf.finalize path is unchanged."""
    metadata = _basic_metadata()
    wf = new_workflow(metadata, source_path=__file__)
    clip = wf.add_node("CLIPTextEncode", text="hi")
    save = wf.add_node("SaveImage", images=[clip.id, 0], filename_prefix="x")
    finalized = wf.finalize(
        {"prompt": InputSpec(node=clip, field="text", default="hi", type="STRING")},
        output_node=save,
        output_type="SaveImage",
        name="image",
        artifact_kind="image",
        mime_type="image/png",
    )
    assert isinstance(finalized, VibeWorkflow)
    assert "prompt" in finalized.inputs


def test_decorator_releases_context_on_error():
    """If build() raises, the ContextVar binding is released."""
    from vibecomfy.workflow_context import active_workflow
    metadata = _basic_metadata()

    @ready_template(metadata, source_path=__file__)
    def build():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        build()
    assert active_workflow() is None
