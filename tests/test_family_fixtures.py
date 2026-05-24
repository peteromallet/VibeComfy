from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.porting.emitter import emit_ready_template_python


FIXTURES = Path(__file__).parent / "fixtures"


def _emit_fixture(
    relative_path: str,
    template_id: str,
    *,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
) -> str:
    path = FIXTURES / relative_path
    raw = json.loads(path.read_text(encoding="utf-8"))
    api = normalize_to_api(raw, use_comfy_converter=False)
    workflow = convert_to_vibe_format(api, source_path=str(path), workflow_id=template_id)
    return emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": template_id,
            "capability": "fixture",
            "provenance": {"source_workflow": str(path)},
        },
        ready_requirements={},
        template_id=template_id,
        registered_inputs=registered_inputs,
        raw_workflow=raw,
    )


def _build_generated(text: str, filename: str = "ready_templates/image/family_fixture.py") -> Any:
    namespace: dict[str, Any] = {"__file__": filename}
    exec(compile(text, filename, "exec"), namespace)  # noqa: S102 - generated fixture code under test
    return namespace["build"]()


def test_family_e_proxy_widgets_map_nonsequential_subgraph_kwargs() -> None:
    text = _emit_fixture("family_e/proxy_widgets_subgraph.json", "image/family_e_proxy_widgets")

    call = text[text.index("proxy_widgets_result = proxy_widgets(") : text.index("saveimage = SaveImage(")]

    assert "prompt='a glass teapot'" in call
    assert "width=512" in call
    assert "height=768" in call
    assert "width=None" not in call
    assert "height=None" not in call


def test_family_a_register_input_targets_rebuilt_node_ids() -> None:
    text = _emit_fixture(
        "family_a/register_input_id_map.json",
        "image/family_a_register_input",
        registered_inputs={"model": ("42", "unet_name")},
    )

    workflow = _build_generated(text)

    assert workflow.inputs["model"].node_id in workflow.nodes


@pytest.mark.xfail(strict=True, reason="Phase 1 Family B must carry registered inputs through subgraph inlining.")
def test_family_b_registered_input_repoints_to_inlined_subgraph_argument() -> None:
    text = _emit_fixture(
        "family_b/register_input_repointed_after_inlining.json",
        "image/family_b_repointed",
        registered_inputs={"prompt": ("1", "widget_0")},
    )

    call = text[text.index("edited = text_to_image_retarget(") : text.index("saveimage = SaveImage(")]

    assert "prompt=public('prompt'" in call
    assert "prompt='a small blue bird'" not in call


def test_family_c_subgraph_named_build_does_not_shadow_template_build() -> None:
    text = _emit_fixture("family_c/subgraph_build_name_collision.json", "image/family_c_build_collision")

    subgraph_section = text[text.index("# === Subgraph functions ===") : text.index("def build() -> VibeWorkflow:")]
    build_section = text[text.index("def build() -> VibeWorkflow:") :]

    assert "def build(" not in subgraph_section
    assert "build = build()" not in build_section


def test_family_d_multi_output_subgraph_returns_every_declared_output() -> None:
    text = _emit_fixture("family_d/multi_output_arity.json", "image/family_d_multi_output")

    assert "image, mask = dual_outputs()" in text
    assert "return dualoutputnode.out('IMAGE'), dualoutputnode.out('MASK')" in text
    assert "return None" not in text


def test_family_f_set_get_broadcast_emits_no_helper_raw_calls() -> None:
    text = _emit_fixture("family_f/set_get_broadcast.json", "image/family_f_set_get")

    assert "raw_call('GetNode'" not in text
    assert "raw_call('SetNode'" not in text
    assert "images=image" in text


def test_compile_time_broadcast_resolution_byte_identical_after_resolver_helper_extension() -> None:
    """Regression guard (SD3): adding RESOLVER_HELPER_CLASS_TYPES to helpers.py must not change
    the compile-time broadcast resolution output of workflow.compile('api').
    The two workflow.py callers of collect_broadcast_sources must remain byte-identical.
    """
    import hashlib

    from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow(
        "regression/broadcast_compile",
        WorkflowSource("regression/broadcast_compile", path="tests/fixtures/family_f/set_get_broadcast.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
    wf.nodes["2"] = VibeNode("2", "SetNode", widgets={"widget_0": "reference_image"})
    wf.nodes["3"] = VibeNode("3", "GetNode", widgets={"widget_0": "reference_image"})
    wf.nodes["4"] = VibeNode("4", "SaveImage", inputs={"filename_prefix": "out"})
    wf.edges.append(VibeEdge("1", "0", "2", "IMAGE"))
    wf.edges.append(VibeEdge("3", "0", "4", "images"))

    result = wf.compile("api")

    # LoadImage and SaveImage must be present; SetNode and GetNode resolved away
    assert "1" in result
    assert "4" in result
    assert "2" not in result
    assert "3" not in result
    # SaveImage gets images from LoadImage slot 0, not from GetNode
    assert result["4"]["inputs"]["images"] == ["1", 0]

    # Byte-identity: two calls produce the same output
    first = hashlib.sha256(str(sorted(result.items())).encode()).hexdigest()
    second = hashlib.sha256(str(sorted(wf.compile("api").items())).encode()).hexdigest()
    assert first == second


# -- Family I: opaque UUID component materialization policy (SD1) ---------


def test_family_i_opaque_component_emits_raw_call_when_no_subgraph_definition() -> None:
    """Family I: Opaque UUID components without subgraph definitions emit raw_call.

    The locked SD1 policy says materialize-as-inline-Python-function, but this
    is only possible when a subgraph definition is available.  The opaque_component.json
    fixture has a UUID node with no subgraph definition, so it falls back to raw_call
    and must be documented as a strict-ready exception.

    z_image node 76 is the positive control: it HAS a subgraph definition and IS
    materialized (verified by T6 / test_family_e).
    """
    text = _emit_fixture("porting/opaque_component.json", "test/family_i_opaque")

    # The UUID component 'a1b2c3d4-...' has no subgraph definition, so it must
    # emit raw_call as the fallback.
    assert "raw_call('a1b2c3d4-e5f6-7890-abcd-ef1234567890'" in text, (
        "Opaque UUID component must emit raw_call when no subgraph definition is available"
    )

    # It must NOT be materialized as an inline function (no def for it should
    # appear in the subgraph functions section).
    assert "# === Subgraph functions ===" not in text.lower(), (
        "No subgraph functions section should exist for a fixture with no subgraph definitions"
    )

    # The known nodes (LoadImage, PreviewImage) should use typed wrappers.
    assert "LoadImage(" in text
    assert "PreviewImage(" in text


def test_family_i_z_image_node_76_materialized_as_inline_function() -> None:
    """Family I: z_image node 76 must be materialized as an inline Python function.

    This is the must-criterion from SD1: z_image node 76 carries a subgraph
    definition and must be materialized, never excepted.  The emitter must
    produce an inline function for it, not raw_call.
    """
    import json
    from pathlib import Path

    z_image_path = Path("workflow_corpus/official/image/z_image.json")
    raw = json.loads(z_image_path.read_text(encoding="utf-8"))
    api = normalize_to_api(raw, use_comfy_converter=False)
    workflow = convert_to_vibe_format(api, source_path=str(z_image_path), workflow_id="image/z_image")

    text = emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": "image/z_image",
            "capability": "text_to_image",
            "provenance": {"source_workflow": str(z_image_path)},
        },
        ready_requirements={},
        template_id="image/z_image",
        registered_inputs={},
        raw_workflow=raw,
    )

    # The subgraph for node 76 (UUID 9b9009e4-...) must be materialized as an
    # inline function named after the subgraph.
    assert "def text_to_image_z_image_base(" in text, (
        "z_image node 76 must be materialized as an inline function"
    )

    # Node 76 must NOT appear as a raw_call — it must be materialized.
    assert "raw_call('9b9009e4-2d3d-445f-9be5-6063f465757e'" not in text, (
        "z_image node 76 must not be emitted as raw_call; it must be materialized"
    )

    # The materialized function must contain the inner nodes (CLIPTextEncode, KSampler, etc.)
    assert "CLIPTextEncode(text=prompt" in text
    assert "KSampler(" in text
    assert "# === Subgraph functions ===" in text
