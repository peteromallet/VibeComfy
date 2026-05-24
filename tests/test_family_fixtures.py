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


@pytest.mark.xfail(strict=True, reason="Phase 1 Family E must map proxyWidgets by source field instead of widget position.")
def test_family_e_proxy_widgets_map_nonsequential_subgraph_kwargs() -> None:
    text = _emit_fixture("family_e/proxy_widgets_subgraph.json", "image/family_e_proxy_widgets")

    call = text[text.index("proxy_widgets = proxy_widgets(") : text.index("saveimage = SaveImage(")]

    assert "prompt='a glass teapot'" in call
    assert "width=512" in call
    assert "height=768" in call
    assert "width=None" not in call
    assert "height=None" not in call


@pytest.mark.xfail(strict=True, reason="Phase 1 Family A must remap source IDs before emitting filename-field register_input calls.")
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


@pytest.mark.xfail(strict=True, reason="Phase 1 Family C must avoid subgraph function names that collide with build().")
def test_family_c_subgraph_named_build_does_not_shadow_template_build() -> None:
    text = _emit_fixture("family_c/subgraph_build_name_collision.json", "image/family_c_build_collision")

    subgraph_section = text[text.index("# === Subgraph functions ===") : text.index("def build() -> VibeWorkflow:")]
    build_section = text[text.index("def build() -> VibeWorkflow:") :]

    assert "def build(" not in subgraph_section
    assert "build = build()" not in build_section


@pytest.mark.xfail(strict=True, reason="Phase 1 Family D must preserve multi-output return arity from subgraph links.")
def test_family_d_multi_output_subgraph_returns_every_declared_output() -> None:
    text = _emit_fixture("family_d/multi_output_arity.json", "image/family_d_multi_output")

    assert "image, mask = dual_outputs()" in text
    assert "return dualoutputnode.out('IMAGE'), dualoutputnode.out('MASK')" in text
    assert "return None" not in text


@pytest.mark.xfail(strict=True, reason="Phase 1 Family F must resolve SetNode/GetNode broadcasts before Python emission.")
def test_family_f_set_get_broadcast_emits_no_helper_raw_calls() -> None:
    text = _emit_fixture("family_f/set_get_broadcast.json", "image/family_f_set_get")

    assert "raw_call('GetNode'" not in text
    assert "raw_call('SetNode'" not in text
    assert "images=image" in text
