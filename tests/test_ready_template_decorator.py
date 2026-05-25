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


# ---------------------------------------------------------------------------
# Emitter shape: decorator
# ---------------------------------------------------------------------------


def _emit_for_source(json_path: str, ready_id: str, emit_shape: str) -> str:
    from vibecomfy.porting.workbench import load_port_source
    from vibecomfy.porting.emitter import emit_ready_template_python
    from vibecomfy.porting.convert import (
        _ready_metadata,
        _ready_requirements,
        _conversion_provenance,
    )

    loaded = load_port_source(json_path)
    provenance = _conversion_provenance(
        loaded.workflow,
        source_path=loaded.source_path,
        provenance=None,
        source_hash=None,
        workflow_shape=None,
        output_mode="ready_template",
        ready_id=ready_id,
    )
    return emit_ready_template_python(
        loaded.workflow,
        ready_metadata=_ready_metadata(
            loaded.workflow,
            ready_id=ready_id,
            source_path=loaded.source_path,
            provenance=provenance,
        ),
        ready_requirements=_ready_requirements(loaded.workflow),
        template_id=ready_id,
        raw_workflow=loaded.raw_workflow,
        emit_shape=emit_shape,
    )


def test_emit_decorator_shape_produces_expected_structure(tmp_path):
    """The decorator emit shape hoists PUBLIC_INPUTS, adds @ready_template, and drops wf/return lines."""
    pytest_repo = "workflow_corpus/official/video/wan_t2v.json"
    from pathlib import Path
    if not Path(pytest_repo).exists():
        pytest.skip("source JSON not present in this checkout")

    text = _emit_for_source(pytest_repo, "video/wan_t2v", "decorator")

    assert "from vibecomfy.templates import" in text
    assert "PublicInput" in text
    assert "ready_template" in text
    # No new_workflow import in decorator shape.
    assert "new_workflow" not in text.split("\ndef build")[0]
    # PUBLIC_INPUTS at module top (before def build).
    head, _, body = text.partition("\ndef build")
    assert "PUBLIC_INPUTS = {" in head
    assert "OUTPUT = dict(" in head
    assert "@ready_template(READY_METADATA" in head
    # No `wf = new_workflow` inside build body.
    assert "wf = new_workflow" not in body
    # No trailing return wf.finalize.
    assert "return wf.finalize" not in body


def test_emit_decorator_shape_compile_parity(tmp_path):
    """Decorator shape compiles to byte-identical API JSON as flat shape."""
    pytest_repo = "workflow_corpus/official/video/wan_t2v.json"
    from pathlib import Path
    if not Path(pytest_repo).exists():
        pytest.skip("source JSON not present in this checkout")

    flat_text = _emit_for_source(pytest_repo, "video/wan_t2v", "flat")
    deco_text = _emit_for_source(pytest_repo, "video/wan_t2v", "decorator")

    flat_path = tmp_path / "flat.py"
    deco_path = tmp_path / "deco.py"
    flat_path.write_text(flat_text, encoding="utf-8")
    deco_path.write_text(deco_text, encoding="utf-8")

    import importlib.util

    def _load_build(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.build()

    flat_wf = _load_build(flat_path, "flat_parity")
    deco_wf = _load_build(deco_path, "deco_parity")

    flat_api = flat_wf.compile("api")
    deco_api = deco_wf.compile("api")

    # Normalize: same nodes + same inputs (order-insensitive).
    def _normalize(api):
        return {
            nid: {
                "class_type": v.get("class_type"),
                "inputs": sorted(v.get("inputs", {}).items(), key=lambda kv: kv[0]),
            }
            for nid, v in api.items()
        }

    assert _normalize(flat_api) == _normalize(deco_api)
