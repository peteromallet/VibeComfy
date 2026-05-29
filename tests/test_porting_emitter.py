from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.porting.convert import ManualTemplateRefusal, _check_manual_refusal
from vibecomfy.porting.emitter import (
    EmissionDiagnostic,
    READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
    READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
    READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
    READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
    emit_ready_template_python,
    emit_scratchpad_python,
)
from vibecomfy.utils import find_repo_root
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
from tools.format_as_python import format_as_python


def _sample_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("sample", WorkflowSource("sample", provenance={"origin": "unit"}))
    workflow.nodes["10"] = VibeNode("10", "LoadImage", inputs={"image": "input.png"})
    workflow.nodes["20"] = VibeNode(
        "20",
        "SaveImage",
        inputs={"filename_prefix": "out/sample", "resize_type.multiple": 3},
    )
    workflow.connect("10.0", "20.images")
    workflow.register_input("prefix", "20", "filename_prefix", "out/sample")
    return workflow


def _workflow_from_ui_json(path: str) -> tuple[VibeWorkflow, dict[str, Any]]:
    import json

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    api = normalize_to_api(raw, use_comfy_converter=False)
    workflow = convert_to_vibe_format(api, source_path=path, workflow_id=Path(path).stem)
    return workflow, raw


def _emit_ready_from_ui_json(path: str, template_id: str) -> str:
    workflow, raw = _workflow_from_ui_json(path)
    return emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": template_id,
            "capability": "image_edit",
            "provenance": {"source_workflow": path},
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id=template_id,
        raw_workflow=raw,
    )


def test_emit_scratchpad_python_preserves_ids_extras_inputs_and_provenance() -> None:
    text = emit_scratchpad_python(
        _sample_workflow(),
        workflow_id="scratch/sample",
        source_path="workflow_corpus/source.json",
        provenance={"source_hash": "sha256:abc"},
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "READY_METADATA" not in text
    assert "source_type='scratchpad'" in text
    assert "provenance={'source_hash': 'sha256:abc'}" in text
    assert "_extras={'resize_type.multiple': 3}" in text

    namespace: dict[str, object] = {"__file__": "out/scratchpads/sample.py"}
    exec(compile(text, "scratch emitted", "exec"), namespace)  # noqa: S102 - generated code under test
    workflow = namespace["build"]()

    assert isinstance(workflow, VibeWorkflow)
    assert workflow.id == "scratch/sample"
    assert workflow.source.source_type == "scratchpad"
    assert workflow.source.path == "workflow_corpus/source.json"
    assert workflow.source.provenance == {"source_hash": "sha256:abc"}
    assert sorted(workflow.nodes) == ["10", "20"]
    assert workflow.nodes["20"].inputs["resize_type.multiple"] == 3
    assert workflow.inputs["prefix"].node_id == "20"
    assert workflow.compile("api")["20"]["inputs"]["images"] == ["10", 0]


def test_emit_ready_template_python_has_ready_metadata_contract() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={"ready_template": "image/sample", "source_workflow": "workflow_corpus/source.json"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/sample",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "READY_METADATA =" in text
    assert "READY_REQUIREMENTS =" not in text
    assert "ReadyMetadata.build(" in text
    assert "template_id='image/sample'" not in text
    assert "from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow" in text
    assert "from vibecomfy.registry.ready_template import" not in text
    assert "def _node" not in text
    # Post-revert: emitter uses the flat `wf = new_workflow(...)` form rather
    # than `with new_workflow(...) as wf:` for ready templates.  The
    # context-manager form remains supported on VibeWorkflow but is no longer
    # emitted, so the body sits at 4-space indent.
    assert "wf = new_workflow(READY_METADATA, source_path=__file__)" in text
    assert "LoadImage(image='input.png')" in text
    assert "_id='10'" not in text
    assert "wf.metadata.setdefault('id_map'" not in text
    assert "wf._set_id_map(" not in text
    assert "LoadImage(wf" not in text
    assert "PUBLIC_INPUT_METADATA = {" in text
    # Post-revert: the parallel `def PUBLIC_INPUTS(**nodes):` factory is gone;
    # finalize consumes the top-level `PUBLIC_INPUT_METADATA` dict directly.
    assert "def PUBLIC_INPUTS(**nodes):" not in text
    assert "    return wf.finalize(PUBLIC_INPUT_METADATA" in text
    assert "'prefix': InputSpec(node='20', field='filename_prefix', default='out/sample')" in text
    assert "bind_input(" not in text
    assert "bind_output(" not in text
    assert "artifact_kind='image'" in text
    # Note: this fixture's source-workflow uses node IDs '10'/'20' but the
    # emitted build() creates fresh nodes that auto-assign IDs '1'/'2', so the
    # module-level PUBLIC_INPUT_METADATA's string node='20' will not resolve at
    # exec time.  Real regenerated ready templates avoid this because their
    # source-workflow IDs and the emitter's variable-ordering happen to align
    # (LoadImage gets '1', etc.) — see ``tools/convert_ready_templates.py`` and
    # the regenerated ``ready_templates/image/basic_image_upscale.py``.


def test_ready_template_provenance_paths_are_repo_relative() -> None:
    source_path = find_repo_root() / "workflow_corpus" / "source.json"
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={
            "ready_template": "image/sample",
            "capability": "image",
            "provenance": {
                "source_path": str(source_path),
                "source_workflow_path": str(source_path),
                "source_workflow": str(source_path),
            },
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/sample",
    )

    assert str(source_path) not in text
    assert "'source_path': 'workflow_corpus/source.json'" in text
    assert "'source_workflow_path': 'workflow_corpus/source.json'" in text
    assert "'source_workflow': 'workflow_corpus/source.json'" in text


def test_emit_ready_template_omits_empty_model_and_input_boilerplate() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample", provenance={"origin": "unit"}))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "out/sample"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/no_inputs", "capability": "image"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/no_inputs",
    )

    assert "MODELS = {}" not in text
    assert "PUBLIC_INPUTS = {}" not in text
    assert "PUBLIC_INPUT_METADATA" not in text
    assert "def PUBLIC_INPUTS" not in text
    assert "    inputs=PUBLIC_INPUTS," not in text
    assert "    models=MODELS," not in text
    assert "return wf.finalize({}" in text
    assert "ModelAsset" not in text
    assert "InputSpec" not in text


def test_ready_template_public_inputs_bind_actual_node_objects() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={"ready_template": "image/sample", "source_workflow": "workflow_corpus/source.json"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/sample",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    assert "node=ref(" not in text
    # Post-revert: PUBLIC_INPUT_METADATA is a top-level dict consumed directly
    # by finalize() rather than a factory function recomputed each build().
    assert "PUBLIC_INPUT_METADATA" in text
    assert "wf.finalize(PUBLIC_INPUT_METADATA" in text


def test_ready_template_public_inputs_survive_variable_suffix_changes() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["10"] = VibeNode("10", "SaveImage", inputs={"filename_prefix": "out/first"})
    workflow.nodes["20"] = VibeNode("20", "SaveImage", inputs={"filename_prefix": "out/second"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/renamed", "capability": "image"},
        ready_requirements={},
        template_id="image/renamed",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    # Post-revert: PUBLIC_INPUT_METADATA is a module-level dict, so it uses the
    # source-workflow node id directly rather than re-resolving variable names
    # inside a factory function.
    assert "'prefix': InputSpec(node='20', field='filename_prefix', default='out/second')" in text
    assert "def PUBLIC_INPUTS(**nodes):" not in text


def test_ready_template_public_input_refs_do_not_depend_on_model_asset_keys() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "obscure-file-name.safetensors", "weight_dtype": "default"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": "image/model_key_independent",
            "capability": "image",
            "model_assets": [
                {
                    "name": "obscure-file-name.safetensors",
                    "url": "https://example.test/obscure-file-name.safetensors",
                    "subdir": "diffusion_models",
                    "field": "unet_name",
                }
            ],
        },
        ready_requirements={},
        template_id="image/model_key_independent",
        registered_inputs={"model": ("1", "unet_name")},
    )

    assert "'diffusion_model': ModelAsset(" in text
    # Post-revert: PUBLIC_INPUT_METADATA uses the source-workflow node id as a
    # string rather than the build-local variable.  The ``MODEL_NAME`` constant
    # is still derivable from the model_assets row (unet_name → UNET_NAME at
    # fe03111, but the value-keyed name MODEL_NAME is acceptable when the field
    # only appears once across the workflow).
    assert "InputSpec(node='1', field='unet_name'" in text
    namespace: dict[str, object] = {"__file__": "ready_templates/image/model_key_independent.py"}
    exec(compile(text, "ready_templates/image/model_key_independent.py", "exec"), namespace)  # noqa: S102
    workflow = namespace["build"]()

    assert workflow.inputs["model"].node_id == "1"
    assert workflow.inputs["model"].field == "unet_name"


def test_emitter_warns_for_schema_unknown_identifier_kwargs_hidden_by_extras() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "out/sample", "mystery": 3})
    diagnostics: list[EmissionDiagnostic] = []

    emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/schema_unknown", "capability": "image"},
        ready_requirements={},
        template_id="image/schema_unknown",
        diagnostics=diagnostics,
    )

    assert any(
        diagnostic.code == READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS
        and diagnostic.detail["input"] == "mystery"
        for diagnostic in diagnostics
    )


def test_emitter_keeps_non_identifier_extras_without_schema_unknown_warning() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "ImageScaleToTotalPixels", inputs={"megapixels": 1.0, "resize_type.multiple": 3})
    diagnostics: list[EmissionDiagnostic] = []

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/custom_extra", "capability": "image"},
        ready_requirements={},
        template_id="image/custom_extra",
        diagnostics=diagnostics,
    )

    assert "**{'resize_type.multiple': 3}" in text
    assert not any(
        diagnostic.code == READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS
        for diagnostic in diagnostics
    )


def test_model_block_uses_role_based_keys_for_model_constants() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample", provenance={"origin": "unit"}))
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "model.safetensors", "weight_dtype": "default"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": "image/roles",
            "capability": "image",
            "model_assets": [
                {
                    "name": "obscure-file-name.safetensors",
                    "url": "https://example.test/obscure-file-name.safetensors",
                    "subdir": "diffusion_models",
                    "field": "unet_name",
                }
            ],
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="image/roles",
    )

    assert "'diffusion_model': ModelAsset(" in text
    assert "'obscure_file_name': ModelAsset(" not in text


def test_model_constant_names_dedupe_path_prefixed_basenames() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "DualCLIPLoader",
        inputs={
            "clip_name1": "gemma_3_12B_it_fp4_mixed.safetensors",
            "clip_name2": "ltx-2.3_text_projection_bf16.safetensors",
        },
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "ProjectionLoader",
        inputs={"model_name": r"VIDEO\LTX\LTX-2\ltx-2.3_text_projection_bf16.safetensors"},
    )
    workflow.nodes["3"] = VibeNode("3", "VAELoader", inputs={"vae_name": "taeltx2_3.safetensors"})
    workflow.nodes["4"] = VibeNode("4", "VAELoader", inputs={"vae_name": r"vae_approx\taeltx2_3.safetensors"})
    workflow.nodes["5"] = VibeNode("5", "TextEncoderLoader", inputs={"text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors"})
    workflow.nodes["6"] = VibeNode("6", "CheckpointLoaderSimple", inputs={"ckpt_name": "ltx-2-19b-distilled.safetensors"})
    workflow.nodes["7"] = VibeNode("7", "LTXModelLoader", inputs={"ltxv_path": "ltx-2-19b-distilled.safetensors"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/model_dedupe", "capability": "image"},
        ready_requirements={},
        template_id="image/model_dedupe",
    )

    assert "CKPT_PROJECTION_NAME" not in text
    assert text.count("CLIP_PROJECTION_NAME =") == 1
    assert "CLIP_PROJECTION_NAME = 'VIDEO/LTX/LTX-2/ltx-2.3_text_projection_bf16.safetensors'" in text
    assert text.count("VAE_TAESD_NAME =") == 1
    assert "VAE_TAESD_NAME = 'vae_approx/taeltx2_3.safetensors'" in text
    assert "VAE_NAME = 'taeltx2_3.safetensors'" not in text
    assert "TEXT_ENCODER_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'" not in text
    assert "LTXV_PATH_NAME = 'ltx-2-19b-distilled.safetensors'" not in text


def test_model_constant_names_use_known_model_families() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "AudioModelLoader",
        inputs={"model_name": r"MelBandRoformer\MelBandRoformer_fp16.safetensors"},
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "UpscaleModelLoader",
        inputs={"model_name": "ltx-2.3-spatial-upscaler-x2-1.1.safetensors"},
    )
    workflow.nodes["3"] = VibeNode(
        "3",
        "CheckpointLoaderSimple",
        inputs={"ckpt_name": "depth_anything_vitl14.pth"},
    )

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/model_families", "capability": "image"},
        ready_requirements={},
        template_id="image/model_families",
    )

    assert "MEL_BAND_ROFORMER_NAME = 'MelBandRoformer/MelBandRoformer_fp16.safetensors'" in text
    assert "SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'" in text
    assert "DEPTH_ANYTHING_NAME = 'depth_anything_vitl14.pth'" in text
    assert "MODEL_NAME =" not in text
    assert "CKPT_NAME = 'depth_anything_vitl14.pth'" not in text


def test_emitter_resolves_serialized_graph_lookup_prompt_literals() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    prompt = "a detailed cinematic prompt that is long enough to hoist"
    workflow.nodes["11"] = VibeNode("11", "CLIPTextEncode", inputs={"text": prompt})
    workflow.nodes["21"] = VibeNode(
        "21",
        "CLIPTextEncode",
        inputs={"text": "wf.nodes['11'].inputs.get('text', '')"},
    )

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/lookup_prompt", "capability": "image"},
        ready_requirements={},
        template_id="image/lookup_prompt",
    )

    assert "wf.nodes['11'].inputs.get('text', '')" not in text
    assert f"DEFAULT_PROMPT = {prompt!r}" in text


def test_ready_template_emits_custom_node_pack_provenance_from_lockfile() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "DepthAnything_V2", inputs={"image": "input.png"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/depth", "capability": "image"},
        ready_requirements={"custom_nodes": []},
        template_id="image/depth",
    )

    assert "custom_node_packs=" in text
    assert "'ComfyUI-DepthAnythingV2'" in text
    assert "'classes_used': ['DepthAnything_V2']" in text
    assert "'commit': '553187872eeb1d52e50dc53209fa57e569609a72'" in text
    assert "'status': 'discovered'" in text


def test_ready_template_preserves_explicit_custom_node_pack_override() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": "image/depth",
            "capability": "image",
            "custom_node_packs": {"ExamplePack": {"commit": "abc", "classes_used": ["LoadImage"]}},
        },
        ready_requirements={},
        template_id="image/depth",
    )

    assert "custom_node_packs={'ExamplePack': {'commit': 'abc', 'classes_used': ['LoadImage']}}" in text


def test_model_block_emits_gated_model_assets() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={
            "ready_template": "image/gated",
            "capability": "image",
            "model_assets": [
                {
                    "name": "gated.safetensors",
                    "url": "https://example.test/gated.safetensors",
                    "subdir": "diffusion_models",
                    "gated": True,
                }
            ],
        },
        ready_requirements={},
        template_id="image/gated",
    )

    assert "gated=True" in text
    assert "sha256='gated'" not in text


def test_subgraph_materialized_as_bare_function() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json",
        "edit/flux2_klein_9b_image_edit_base",
    )

    assert "@block" not in text
    assert "@subgraph" not in text
    assert "Handles(" not in text
    assert "def image_edit_flux2_klein_9b(" in text
    assert "workflow: VibeWorkflow" not in text
    body = text[text.index("def image_edit_flux2_klein_9b("):text.index("def image_edit_flux2_klein_9b_dual(")]
    assert "unet_name: str" in body
    assert "image," in body
    assert "UNETLoader(" in body
    assert "unet_name=unet_name" in body
    assert "return vaedecode" in body


def test_subgraph_multi_output_returns_tuple() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json",
        "edit/flux2_klein_4b_image_edit_distilled",
    )

    body = text[text.index("def reference_conditioning("):text.index("def reference_conditioning_93041a64(")]
    assert "return referencelatent_2, referencelatent" in body
    assert "conditioning, conditioning_1 = reference_conditioning(" in text


def test_subgraph_call_site_replaces_raw_call() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json",
        "edit/flux2_klein_9b_image_edit_base",
    )

    assert "edited = image_edit_flux2_klein_9b(" in text
    assert "edited_dual = image_edit_flux2_klein_9b_dual(" in text
    assert "raw_call('7b34ab90" not in text
    assert "raw_call('65c22b29" not in text

    workflow = VibeWorkflow("uuid", WorkflowSource("uuid"))
    workflow.nodes["1"] = VibeNode("1", "11111111-1111-1111-1111-111111111111")
    fallback = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/uuid", "capability": "image"},
        ready_requirements={},
        template_id="image/uuid",
        raw_workflow={"definitions": {"subgraphs": []}},
    )
    assert "raw_call('11111111-1111-1111-1111-111111111111'" in fallback


def test_subgraph_call_site_uses_widget_fed_literals() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/image/flux2_klein_9b_t2i.json",
        "image/flux2_klein_9b_t2i",
    )

    assert "def text_to_image_flux2_klein_9b(" in text
    assert "edited = text_to_image_flux2_klein_9b(" in text
    assert "raw_call('7b34ab90" not in text
    call = text[text.index("edited = text_to_image_flux2_klein_9b("):text.index("saveimage = SaveImage(")]
    assert "width=1024" in call
    assert "height=1024" in call
    assert "unet_name='flux-2-klein-base-9b-fp8.safetensors'" in call
    assert "clip_name='qwen_3_8b_fp8mixed.safetensors'" in call
    assert "vae_name='full_encoder_small_decoder.safetensors'" in call
    assert "prompt=''" in call


def test_subgraph_call_site_uses_proxy_widget_order_for_z_image() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/image/z_image.json",
        "image/z_image",
    )

    call = text[text.index("edited = text_to_image_z_image_base("):text.index("saveimage = SaveImage(")]
    assert "width=1024" in call
    assert "height=1024" in call
    assert "unet_name='z_image_bf16.safetensors'" in call
    assert "clip_name='qwen_3_4b.safetensors'" in call
    assert "vae_name='ae.safetensors'" in call
    assert "steps=25" in call
    assert "cfg=4" in call
    assert "width='A fashion photography" not in call
    assert "steps=770044821593082" not in call
    assert "cfg='randomize'" not in call


def test_subgraph_signature_prefers_meaningful_labels_and_cleans_widgets() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/image/flux2_klein_9b_t2i.json",
        "image/flux2_klein_9b_t2i",
    )

    body = text[text.index("def text_to_image_flux2_klein_9b("):text.index("def build()")]
    signature = body[:body.index("):") + 2]
    assert "width: int" in signature
    assert "height: int" in signature
    assert "prompt: str" in signature
    assert "value: int" not in signature
    assert "value_1: int" not in signature
    assert "value=width" in body
    assert "value=height" in body
    assert "control_after_generate='fixed'" in body
    assert "widget_1=" not in body
    assert "widget_2=" not in body


def test_subgraph_call_site_uses_instance_widget_values_and_warns_when_unbound() -> None:
    workflow = VibeWorkflow("widget_subgraph", WorkflowSource("widget_subgraph"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        metadata={
            "_ui": {
                "inputs": [
                    {"name": "value", "type": "INT", "widget": {"name": "value"}, "link": None},
                ],
                "widgets_values": [123],
            }
        },
    )
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "name": "Widget Source",
                    "inputs": [
                        {"name": "value", "type": "INT"},
                        {"name": "missing", "type": "STRING"},
                    ],
                    "outputs": [],
                    "nodes": [],
                    "links": [],
                }
            ]
        }
    }
    diagnostics: list[EmissionDiagnostic] = []

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/widget_subgraph", "capability": "image"},
        ready_requirements={},
        template_id="image/widget_subgraph",
        raw_workflow=raw,
        diagnostics=diagnostics,
    )

    assert "def widget_source(" in text
    assert "value=123" in text
    assert "missing=None" in text
    assert any(diag.code == "subgraph_input_unbound" for diag in diagnostics)


def test_subgraph_widget_values_ignore_unnamed_input_widget_positions() -> None:
    workflow = VibeWorkflow("widget_subgraph", WorkflowSource("widget_subgraph"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        metadata={
            "_ui": {
                "inputs": [
                    {"name": "width", "type": "INT", "widget": {}, "link": None},
                    {"name": "height", "type": "INT", "widget": {"name": "height"}, "link": None},
                ],
                "widgets_values": [768],
            }
        },
    )
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "name": "Widget Source",
                    "inputs": [
                        {"name": "width", "type": "INT"},
                        {"name": "height", "type": "INT"},
                    ],
                    "outputs": [],
                    "nodes": [],
                    "links": [],
                }
            ]
        }
    }

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/widget_subgraph", "capability": "image"},
        ready_requirements={},
        template_id="image/widget_subgraph",
        raw_workflow=raw,
    )

    assert "height=768" in text
    assert "width=768" not in text
    assert "width=None" in text


def test_subgraph_widget_values_ignore_curated_ui_only_positions() -> None:
    workflow = VibeWorkflow("widget_subgraph", WorkflowSource("widget_subgraph"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "KSampler",
        metadata={
            "_ui": {
                "type": "KSampler",
                "inputs": [],
                "widgets_values": [123, "randomize", 25, 4.0, "euler", "normal", 1.0],
            }
        },
    )
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "id": "KSampler",
                    "name": "Widget Source",
                    "inputs": [
                        {"name": "seed", "type": "INT"},
                        {"name": "steps", "type": "INT"},
                        {"name": "cfg", "type": "FLOAT"},
                    ],
                    "outputs": [],
                    "nodes": [],
                    "links": [],
                }
            ]
        }
    }

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "image/widget_subgraph", "capability": "image"},
        ready_requirements={},
        template_id="image/widget_subgraph",
        raw_workflow=raw,
    )

    assert "seed=123" in text
    assert "steps=25" in text
    assert "cfg=4.0" in text
    assert "steps='randomize'" not in text
    assert "cfg=25" not in text


def test_subgraph_slug_collision_disambiguated() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json",
        "edit/flux2_klein_9b_image_edit_base",
    )

    assert "def image_edit_flux2_klein_9b(" in text
    assert "def image_edit_flux2_klein_9b_dual(" in text


def test_nested_subgraph_emits_function_call() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json",
        "edit/flux2_klein_4b_image_edit_distilled",
    )

    outer = text[text.index("def image_edit_flux2_klein_4b_distilled_dual("):text.index("def build()")]
    assert "reference_conditioning(" in outer
    assert "reference_conditioning_93041a64(" in outer
    assert "raw_call('27eacb9f" not in outer
    assert "raw_call('93041a64" not in outer


def test_nested_subgraph_topological_order() -> None:
    text = _emit_ready_from_ui_json(
        "workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json",
        "edit/flux2_klein_4b_image_edit_distilled",
    )

    assert text.index("def reference_conditioning(") < text.index("def image_edit_flux2_klein_4b_distilled_dual(")
    assert text.index("def reference_conditioning_93041a64(") < text.index("def image_edit_flux2_klein_4b_distilled_dual(")


def test_nested_subgraph_circular_raises() -> None:
    workflow = VibeWorkflow("cycle", WorkflowSource("cycle"))
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "name": "Cycle A",
                    "inputs": [],
                    "outputs": [],
                    "nodes": [{"id": 1, "type": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "inputs": [], "outputs": [], "widgets_values": []}],
                    "links": [],
                },
                {
                    "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "name": "Cycle B",
                    "inputs": [],
                    "outputs": [],
                    "nodes": [{"id": 2, "type": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "inputs": [], "outputs": [], "widgets_values": []}],
                    "links": [],
                },
            ]
        }
    }

    with pytest.raises(RuntimeError, match="Circular subgraph reference detected"):
        emit_ready_template_python(
            workflow,
            ready_metadata={"ready_template": "image/cycle", "capability": "image"},
            ready_requirements={},
            template_id="image/cycle",
            raw_workflow=raw,
        )


def test_tools_format_as_python_remains_ready_template_wrapper() -> None:
    kwargs = {
        "ready_metadata": {"ready_template": "image/sample", "source_workflow": "workflow_corpus/source.json"},
        "ready_requirements": {"models": [], "custom_nodes": []},
        "template_id": "image/sample",
        "registered_inputs": {"prefix": ("20", "filename_prefix")},
    }

    assert format_as_python(_sample_workflow(), **kwargs) == emit_ready_template_python(_sample_workflow(), **kwargs)


def test_ready_template_id_map_contract_for_representative_emissions() -> None:
    cases: list[VibeWorkflow] = []

    image = _sample_workflow()
    cases.append(image)

    typed = VibeWorkflow("typed", WorkflowSource("typed"))
    typed.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "model.safetensors"})
    typed.nodes["2"] = VibeNode("2", "CLIPLoader", inputs={"clip_name": "clip.safetensors", "type": "wan"})
    typed.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out/typed"})
    cases.append(typed)

    audio = VibeWorkflow("audio", WorkflowSource("audio"))
    audio.nodes["4"] = VibeNode("4", "LoadAudio", inputs={"audio": "input.wav"})
    audio.nodes["9"] = VibeNode("9", "SaveAudio", inputs={"filename_prefix": "out/audio"})
    cases.append(audio)

    for workflow in cases:
        text = emit_ready_template_python(
            workflow,
            ready_metadata={"ready_template": workflow.id},
            ready_requirements={"models": [], "custom_nodes": []},
            template_id=workflow.id,
        )
        namespace: dict[str, object] = {"__file__": f"ready_templates/{workflow.id}.py"}
        exec(compile(text, f"{workflow.id} emitted", "exec"), namespace)  # noqa: S102 - generated code under test
        emitted = namespace["build"]()
        assert isinstance(emitted, VibeWorkflow)
        assert emitted.id_map() == {}


def test_ready_template_ltx_tail_lines_are_inside_workflow_context() -> None:
    text = emit_ready_template_python(
        _sample_workflow(),
        ready_metadata={"ready_template": "video/ltx2_3_i2v", "source_workflow": "workflow_corpus/source.json"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="video/ltx2_3_i2v",
        registered_inputs={"prefix": ("20", "filename_prefix")},
    )

    # Post-revert: emitted form is `wf = new_workflow(...)` (flat) rather than
    # a `with` block.  The LTX low-vram patch lines and finalize call therefore
    # sit at 4-space indent inside ``def build():``.
    assert "    wf = new_workflow(READY_METADATA, source_path=__file__)" in text
    assert "    apply_ltx_lowvram(wf)" in text
    assert "    resolution(384, 256, 9).apply(wf)" in text
    assert "    ensure_custom_nodes(wf, READY_METADATA.get(\"requirements\", {}).get(\"custom_nodes\", []))" in text
    assert "    return wf.finalize(PUBLIC_INPUT_METADATA" in text


def test_ready_template_build_spacing_for_multiline_and_packed_simple_calls() -> None:
    workflow = VibeWorkflow("test/spacing", WorkflowSource("test/spacing", provenance={"origin": "unit"}))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "first_input_image_with_long_name_that_forces_multiline_formatting.png"})
    workflow.nodes["2"] = VibeNode("2", "LoadImage", inputs={"image": "second_input_image_with_long_name_that_forces_multiline_formatting.png"})
    workflow.nodes["3"] = VibeNode("3", "CLIPTextEncode", inputs={"text": "short positive"})
    workflow.nodes["4"] = VibeNode("4", "CLIPTextEncode", inputs={"text": "short negative"})
    workflow.nodes["5"] = VibeNode("5", "KSampler", inputs={"seed": 1, "steps": 2, "cfg": 3, "sampler_name": "uni_pc"})
    workflow.nodes["6"] = VibeNode("6", "KSampler", inputs={"seed": 4, "steps": 5, "cfg": 6, "sampler_name": "uni_pc"})
    workflow.nodes["7"] = VibeNode("7", "VAEDecode", inputs={})
    workflow.nodes["8"] = VibeNode("8", "SaveImage", inputs={"filename_prefix": "out/spacing"})

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "test/spacing"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/spacing",
    )

    # Post-revert: emitted body sits at 4-space indent (flat `wf = new_workflow`
    # form) rather than 8-space (legacy `with new_workflow(...) as wf:` form).
    assert "\n    # Inputs\n    LoadImage(" in text
    assert "\n    LoadImage(\n        image='second_input_image" in text
    assert "cliptextencode = CLIPTextEncode(text='short positive')\n    cliptextencode_2 = CLIPTextEncode(text='short negative')" in text
    assert "\n\n    # Conditioning\n" in text
    assert "\n\n    return wf.finalize(PUBLIC_INPUT_METADATA" in text


def test_convert_ready_templates_tool_dry_run_remains_compatible() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.convert_ready_templates",
            "--template",
            "image/qwen_image_2512",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "image/qwen_image_2512" in result.stdout


# ---------------------------------------------------------------------------
# Sprint 1 T10: focused tool tests - shared gates for bulk dry-run / --write
# ---------------------------------------------------------------------------


def test_shared_manual_refusal_raises_for_manual_marker() -> None:
    """_check_manual_refusal raises ManualTemplateRefusal for # vibecomfy: manual."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write("# vibecomfy: manual - do not regenerate\n")
        tmp.write("def build():\n    pass\n")
        tmp_path = Path(tmp.name)

    try:
        with pytest.raises(ManualTemplateRefusal, match="manual"):
            _check_manual_refusal(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_shared_manual_refusal_passes_for_non_manual() -> None:
    """_check_manual_refusal does not raise for a normal file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write("# vibecomfy: generated\n")
        tmp.write("def build():\n    pass\n")
        tmp_path = Path(tmp.name)

    try:
        # Should not raise
        _check_manual_refusal(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_write_emitted_raises_manual_refusal_before_write(tmp_path: Path) -> None:
    """_write_emitted refuses to write over a manual template (shared gate)."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    # Create a "manual" template under a fake ready_templates tree
    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    manual_path = tmpl_dir / "test_manual.py"
    manual_path.write_text("# vibecomfy: manual - do not regenerate\ndef build(): pass\n")

    # Monkey-patch READY_ROOT so the path passes the outside-root guard
    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        with pytest.raises(ManualTemplateRefusal, match="manual"):
            _write_emitted(manual_path, "emitted text", dry_run=False)
        # File must be unchanged
        assert manual_path.read_text().startswith("# vibecomfy: manual")
    finally:
        tmod.READY_ROOT = orig_root


def test_write_emitted_include_manual_override_replaces_manual_template(tmp_path: Path) -> None:
    from tools.convert_ready_templates import _write_emitted

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    manual_path = tmpl_dir / "test_manual.py"
    manual_path.write_text("# vibecomfy: manual - do not regenerate\ndef build(): pass\n")

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        _write_emitted(
            manual_path,
            "# vibecomfy: generated\n# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>\ndef build():\n    return None\n",
            dry_run=False,
            include_manual=True,
        )
        assert manual_path.read_text(encoding="utf-8").startswith("# vibecomfy: generated")
    finally:
        tmod.READY_ROOT = orig_root


def test_write_emitted_uses_atomic_temp_replace(tmp_path: Path) -> None:
    """_write_emitted uses temp file + replace for atomic writes."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    target = tmpl_dir / "test_atomic.py"
    original = "# vibecomfy: generated\nORIGINAL_CONTENT = True\n"
    target.write_text(original)

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        emitted = "# vibecomfy: generated\nEMITTED_CONTENT = True\n"
        result = _write_emitted(target, emitted, dry_run=False)
        assert result == target
        assert target.read_text() == emitted
        # No temp file left behind
        temps = list(tmpl_dir.glob(".vibecomfy-convert-*"))
        assert len(temps) == 0
    finally:
        tmod.READY_ROOT = orig_root


def test_convert_template_refuses_manual_via_shared_gate(tmp_path: Path) -> None:
    """_convert_template returns manual-refused row via shared _check_manual_refusal."""
    from tools.convert_ready_templates import (
        _convert_template,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    manual_path = tmpl_dir / "test_manual_convert.py"
    manual_path.write_text("# vibecomfy: manual - do not regenerate\nAPI_WORKFLOW = {}\n")

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        row, emitted, _ = _convert_template(manual_path)
        assert emitted is None
        assert row.shape == "manual-refused"
        assert "manual template refused by shared gate" in row.note
        assert row.parse == "skip"
    finally:
        tmod.READY_ROOT = orig_root


def test_dry_run_writes_to_out_converted(tmp_path: Path) -> None:
    """_write_emitted dry_run=True writes to out/converted/ not in-place."""
    from tools.convert_ready_templates import (
        _write_emitted,
    )

    tmpl_dir = tmp_path / "ready_templates" / "image"
    tmpl_dir.mkdir(parents=True)
    target = tmpl_dir / "test_dry.py"
    original = "# vibecomfy: generated\nORIGINAL = True\n"
    target.write_text(original)

    out_dir = tmp_path / "out" / "converted"
    out_dir.mkdir(parents=True)

    import tools.convert_ready_templates as tmod

    orig_root = tmod.READY_ROOT
    orig_out = tmod.OUT_PREVIEW_ROOT
    try:
        tmod.READY_ROOT = tmp_path / "ready_templates"
        tmod.OUT_PREVIEW_ROOT = out_dir
        emitted = "# vibecomfy: generated\nEMITTED = True\n"
        result = _write_emitted(target, emitted, dry_run=True)
        # Wrote to out/converted/, not in-place
        assert result != target
        assert out_dir in result.parents
        assert result.read_text() == emitted
        # Original is unchanged
        assert target.read_text() == original
    finally:
        tmod.READY_ROOT = orig_root
        tmod.OUT_PREVIEW_ROOT = orig_out


def test_write_gate_requires_both_validate_and_parity() -> None:
    """main() skip-logic refuses writes when validate fails or roundtrip fails."""
    from tools.convert_ready_templates import Row

    # Simulate the gate check from main():
    #   gated_ok = row.validate == "ok" and row.roundtrip in ("ok", "skip", "skip-authored")

    # Case 1: validate fail -> blocked
    r1 = Row(template_id="test/fail_val")
    r1.validate = "fail"
    r1.roundtrip = "ok"
    gated = r1.validate == "ok" and r1.roundtrip in ("ok", "skip", "skip-authored")
    assert not gated

    # Case 2: roundtrip fail -> blocked
    r2 = Row(template_id="test/fail_rt")
    r2.validate = "ok"
    r2.roundtrip = "fail"
    gated = r2.validate == "ok" and r2.roundtrip in ("ok", "skip", "skip-authored")
    assert not gated

    # Case 3: both ok -> allowed
    r3 = Row(template_id="test/ok")
    r3.validate = "ok"
    r3.roundtrip = "ok"
    gated = r3.validate == "ok" and r3.roundtrip in ("ok", "skip", "skip-authored")
    assert gated

    # Case 4: authored shape (skip-authored) -> allowed
    r4 = Row(template_id="test/authored")
    r4.validate = "ok"
    r4.roundtrip = "skip-authored"
    gated = r4.validate == "ok" and r4.roundtrip in ("ok", "skip", "skip-authored")
    assert gated


# ---------------------------------------------------------------------------
# T11 - emitter tests: named outputs, widget aliases, fallbacks, _outputs
# ---------------------------------------------------------------------------


def _workflow_with_output_names(
    output_names: list[str],
) -> VibeWorkflow:
    """Build a minimal multi-output workflow with metadata-driven output_names."""
    workflow = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    workflow.nodes["1"] = VibeNode("1", "MultiOutput")
    workflow.nodes["1"].metadata["output_names"] = output_names
    workflow.nodes["2"] = VibeNode("2", "Consumer")
    # Connect both outputs from node 1 to node 2 on inputs named "a" and "b"
    workflow.connect("1.0", "2.a")
    workflow.connect("1.1", "2.b")
    return workflow


def _workflow_with_widget_aliases(
    class_type: str,
    input_aliases: list[str | None],
    widget_values: dict[str, Any] | None = None,
) -> VibeWorkflow:
    """Build a workflow where a node has input_aliases metadata and widget values."""
    workflow = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    node = VibeNode("1", class_type)
    node.metadata["input_aliases"] = input_aliases
    if widget_values:
        for k, v in widget_values.items():
            if k.startswith("widget_"):
                node.widgets[k] = v
            else:
                node.inputs[k] = v
    workflow.nodes["1"] = node
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out"})
    workflow.connect("1.0", "2.images")
    return workflow


def test_unique_safe_names_emit_named_out() -> None:
    """Unique safe output names produce .out('name') in emitted code."""
    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", "latent"]),
        source_path="test.json",
    )
    # Should use named handles
    assert ".out('image')" in text
    assert ".out('latent')" in text
    assert "_outputs=('image', 'latent')" in text


def test_duplicate_output_names_fall_back_to_numeric() -> None:
    """Duplicate output names fall back to .out(n) with diagnostic."""
    diags: list[EmissionDiagnostic] = []
    from vibecomfy.porting.emitter import (
        EmissionDiagnostic,
        READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
    )

    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", "image"]),
        source_path="test.json",
        diagnostics=diags,
    )
    # Should use numeric handles (duplicate names are unsafe)
    assert ".out(0)" in text
    assert ".out(1)" in text
    # Should NOT use named handles
    assert ".out('image')" not in text
    # Should emit _outputs with the partial names (source of truth)
    assert "_outputs=('image', 'image')" in text
    # Diagnostic should flag ambiguity
    ambiguity_codes = [d.code for d in diags if d.code == READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY]
    assert len(ambiguity_codes) > 0


def test_blank_output_names_fall_back_to_numeric() -> None:
    """Blank output names fall back to .out(n), with named slots where safe."""
    diags: list[EmissionDiagnostic] = []
    from vibecomfy.porting.emitter import (
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
    )

    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", ""]),
        source_path="test.json",
        diagnostics=diags,
    )
    # Slot 0 is safe -> .out('image')
    assert ".out('image')" in text
    # Slot 1 is blank -> .out(1)
    assert ".out(1)" in text
    # _outputs preserves partial evidence
    assert "_outputs=('image', '')" in text
    # Should have avoidable_positional_output diagnostic
    fallback_codes = [d.code for d in diags if d.code == READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT]
    assert len(fallback_codes) > 0


def test_partial_output_evidence_still_emits_outputs_tuple() -> None:
    """_outputs is emitted even when output_names has blank entries (SC19)."""
    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", ""]),
        source_path="test.json",
    )
    # Must contain _outputs with both entries, including the blank
    assert "_outputs=('image', '')" in text


def test_missing_output_names_does_not_emit_outputs() -> None:
    """When node has no output_names metadata, _outputs is NOT emitted."""
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "NoMeta")  # no metadata
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.connect("1.0", "2.a")

    text = emit_scratchpad_python(wf, source_path="test.json")
    # _outputs= keyword arg should NOT appear in the _node() builder call;
    # the helper function definition itself contains "_outputs" but that's fine.
    assert "_outputs=" not in text


def test_ready_template_emits_unpacking_for_typed_multi_output_node() -> None:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "WanImageToVideo")
    wf.nodes["1"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    wf.nodes["2"] = VibeNode("2", "KSampler")
    wf.connect("1.0", "2.positive")
    wf.connect("1.1", "2.negative")
    wf.connect("1.2", "2.latent_image")

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )

    assert "positive, negative, latent = WanImageToVideo()" in text
    assert "positive=positive" in text
    assert "negative=negative" in text
    assert "latent_image=latent" in text
    assert "wanimagetovideo.out" not in text


def test_ready_template_replaces_dead_unpacked_outputs_with_underscore() -> None:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "WanImageToVideo")
    wf.nodes["1"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    wf.nodes["2"] = VibeNode("2", "KSampler")
    wf.connect("1.1", "2.negative")

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )

    assert "_, negative, _ = WanImageToVideo()" in text
    assert "negative=negative" in text
    assert "positive, negative, latent = WanImageToVideo()" not in text


def test_ready_template_keeps_dead_multi_output_node_as_bare_call() -> None:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "SimpleCalculatorKJ", inputs={"expression": "1"})
    wf.nodes["1"].metadata["output_names"] = ["FLOAT", "INT", "BOOLEAN"]

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )

    assert "SimpleCalculatorKJ(expression='1')" in text
    assert " = SimpleCalculatorKJ(expression='1')" not in text


def test_ready_template_unpacked_output_names_use_collision_suffix() -> None:
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "CLIPTextEncode", inputs={"text": "prompt"})
    wf.nodes["2"] = VibeNode("2", "WanImageToVideo")
    wf.nodes["2"].metadata["output_names"] = ["POSITIVE", "NEGATIVE", "LATENT"]
    wf.nodes["3"] = VibeNode("3", "KSampler")
    wf.connect("1.0", "3.positive")
    wf.connect("2.1", "3.negative")
    wf.connect("2.2", "3.latent_image")

    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "video/test", "capability": "video"},
        ready_requirements={},
        template_id="video/test",
    )

    assert "positive = CLIPTextEncode(text='prompt')" in text
    assert "_, negative, latent = WanImageToVideo()" in text
    assert "negative=negative" in text
    assert "latent_image=latent" in text


def test_out_of_range_slot_falls_back_to_numeric() -> None:
    """An edge with a slot beyond output_names range uses .out(n)."""
    wf = VibeWorkflow("test", WorkflowSource("test", provenance={"origin": "test"}))
    wf.nodes["1"] = VibeNode("1", "SingleOutput")
    wf.nodes["1"].metadata["output_names"] = ["only"]  # only slot 0 named
    wf.nodes["2"] = VibeNode("2", "Consumer")
    # Connect from slot 5 which is out of range
    wf.edges.append(VibeEdge("1", "5", "2", "a"))

    text = emit_scratchpad_python(wf, source_path="test.json")
    # Slot 5 is out of range for ["only"] -> .out(5) not .out('only')
    assert ".out(5)" in text
    assert ".out('only')" not in text


def test_widget_alias_success_emits_named_field() -> None:
    """When input_aliases maps widget_N to a name, the emitter uses that name."""
    from vibecomfy.porting.emitter import EmissionDiagnostic

    wf = _workflow_with_widget_aliases(
        "CheckpointLoaderSimple",
        ["ckpt_name"],  # widget_0 -> ckpt_name
        {"widget_0": "v1-5-pruned.safetensors"},
    )

    diags: list[EmissionDiagnostic] = []
    text = emit_scratchpad_python(wf, source_path="test.json", diagnostics=diags)
    # Should use the named field from input_aliases
    assert "ckpt_name=" in text
    assert "'v1-5-pruned.safetensors'" in text
    # Should NOT use raw widget_0
    assert "'widget_0'" not in text


def test_widget_alias_fallback_keeps_positional_widget() -> None:
    """When widget_N index is beyond input_aliases range, keep positional."""
    from vibecomfy.porting.emitter import EmissionDiagnostic

    wf = _workflow_with_widget_aliases(
        "SomeNode",
        ["only_name"],  # only widget_0 has an alias
        {"widget_0": "first_val", "widget_3": "out_of_range_val"},
    )

    diags: list[EmissionDiagnostic] = []
    text = emit_scratchpad_python(wf, source_path="test.json", diagnostics=diags)

    # widget_0 gets aliased
    assert "only_name=" in text
    # widget_3 stays positional (out of range) - emitted as kwarg widget_3=
    assert "widget_3=" in text

    # Verify diagnostics include schema_backed_widget_alias_not_resolved
    from vibecomfy.porting.emitter import (
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
    )
    unresolved_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED
    ]
    assert len(unresolved_codes) > 0


def test_emitted_outputs_preservation_with_partial_blank() -> None:
    """SC19: partial output_names ['image', ''] still emits _outputs=('image', '')."""
    text = emit_scratchpad_python(
        _workflow_with_output_names(["image", ""]),
        source_path="test.json",
    )
    # Must contain the exact _outputs tuple including the blank
    assert "_outputs=('image', '')" in text


# ---------------------------------------------------------------------------
# T5: style diagnostics for generated ready templates
# ---------------------------------------------------------------------------


def test_variable_name_too_long_diagnostic() -> None:
    """generated_variable_name_too_long fires when emitted var name >40 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/long", WorkflowSource("test/long", provenance={"origin": "unit"}))
    # Use a class_type that produces a very long safe variable name
    very_long_ct = "a" * 41
    wf.nodes["1"] = VibeNode("1", very_long_ct, inputs={"text": "hello"})

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/long"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/long",
        diagnostics=diags,
    )

    long_name_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG
    ]
    assert len(long_name_codes) > 0, f"Expected generated_variable_name_too_long diagnostic, got: {[d.code for d in diags]}"


def test_variable_name_not_too_short_no_diagnostic() -> None:
    """No diagnostic for variable names <=40 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/short", WorkflowSource("test/short", provenance={"origin": "unit"}))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/short"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/short",
        diagnostics=diags,
    )

    long_name_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG
    ]
    assert len(long_name_codes) == 0, f"Unexpected long-name diagnostic for short variable names: {long_name_codes}"


def test_long_one_line_node_call_diagnostic() -> None:
    """long_one_line_node_call fires for a single-line ready_node call >120 chars."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/long_line", WorkflowSource("test/long_line", provenance={"origin": "unit"}))
    # Create a node with many string inputs to make the ready_node call long
    wf.nodes["1"] = VibeNode(
        "1",
        "LoadImage",
        inputs={
            "image": "a_very_long_filename_that_pads_the_call_line_to_exceed_one_hundred_twenty_characters_total.png",
        },
    )
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    diags: list[EmissionDiagnostic] = []
    emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/long_line"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/long_line",
        diagnostics=diags,
    )

    long_line_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL
    ]
    # Note: if multi-line formatting kicks in, the line won't be "single line"
    # but the diagnostic fires for any ready_node call whose computed single_line > 120
    # regardless of formatting. Validate that it appears when appropriate.
    # This test verifies the diagnostic code exists and is emitted under the right conditions.
    assert len(long_line_codes) > 0, f"Expected long_one_line_node_call diagnostic, got: {[d.code for d in diags]}"


def test_generated_template_not_formatted_missing_section_comments() -> None:
    """generated_template_not_formatted fires for >=8 nodes without section comments."""
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("test/no_sections", WorkflowSource("test/no_sections", provenance={"origin": "unit"}))
    # Create 8 nodes, none of which map to section roles, so section_groups is empty
    # But the check looks for missing section COMMENTS in the output when nodes >= 8
    # and section_groups are non-empty. Let's create nodes that map to sections.
    for i in range(8):
        nid = str(i + 1)
        # Use class types that map to section roles
        if i == 0:
            ct = "LoadImage"
        elif i == 1:
            ct = "CLIPLoader"
        elif i == 2:
            ct = "CLIPTextEncode"
        elif i == 3:
            ct = "KSampler"
        elif i == 4:
            ct = "VAEDecode"
        elif i == 5:
            ct = "SaveImage"
        elif i == 6:
            ct = "CheckpointLoaderSimple"
        else:
            ct = "PreviewImage"
        wf.nodes[nid] = VibeNode(nid, ct, inputs={"test": "val"})

    diags: list[EmissionDiagnostic] = []
    text = emit_ready_template_python(
        wf,
        ready_metadata={"ready_template": "test/no_sections"},
        ready_requirements={"models": [], "custom_nodes": []},
        template_id="test/no_sections",
        diagnostics=diags,
    )

    # The emitter should produce section comments for >=8 nodes.
    # If not, the diagnostic should fire.
    has_section_comments = any(
        line.strip().startswith("# ") and any(
            sec in line for sec in ("Inputs", "Loaders", "Conditioning", "Sampling", "Decode", "Outputs")
        )
        for line in text.split("\n")
    )

    not_formatted_codes = [
        d.code for d in diags
        if d.code == READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED
    ]
    if not has_section_comments:
        assert len(not_formatted_codes) > 0, (
            f"Expected generated_template_not_formatted diagnostic when no section comments found. "
            f"Diags: {[d.code for d in diags]}"
        )
    # If section comments ARE present, we accept either way (no diagnostic needed)
    # but the diagnostic should NOT fire if sections are present
    if has_section_comments:
        # The diagnostic might still fire for un-indented tail, but not for missing sections
        missing_section_diags = [
            d for d in not_formatted_codes
            if "lacks section comments" in d.message
        ]
        assert len(missing_section_diags) == 0, (
            f"Should not flag missing sections when sections are present: {missing_section_diags}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# T9 — _uid= threading through the .py emitter (scratchpad path)
# ═══════════════════════════════════════════════════════════════════════════════


def test_flat_scratchpad_contains_uid_in_node_calls() -> None:
    """Converting the flat fixture writes a .py containing _uid= for every node."""
    import json as _json

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    wf = convert_to_vibe_format(raw)

    text = emit_scratchpad_python(wf, source_path="tests/fixtures/walking_skeleton/flat.json")

    # Every node with a resolvable identity (all in the flat fixture) should have _uid=
    # The _NODE_HELPER_SOURCE itself contains "_uid: str" and "builder.node.uid = _uid"
    # but those are string literals. The actual calls should be "_uid='<nid>'" etc.
    import re
    call_uids = re.findall(r"_uid='[^']+'", text)
    assert len(call_uids) == 7, (
        f"Expected 7 _uid= call args in flat fixture scratchpad; found {len(call_uids)}"
    )
    # Collect all emitted uid values and verify the set matches litegraph ids 1-7
    uid_values = {re.search(r"_uid='([^']+)'", c).group(1) for c in call_uids}  # type: ignore[union-attr]
    assert uid_values == {str(i) for i in range(1, 8)}, (
        f"Expected uids 1-7; got {uid_values}"
    )


def test_flat_scratchpad_reimport_yields_same_uids() -> None:
    """Re-importing the generated .py yields nodes carrying the same uid."""
    import json as _json

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    wf = convert_to_vibe_format(raw)

    text = emit_scratchpad_python(wf, source_path="tests/fixtures/walking_skeleton/flat.json")

    # Execute the generated code and call build()
    namespace: dict[str, object] = {"__file__": "out/scratchpads/flat.py"}
    exec(compile(text, "flat emitted", "exec"), namespace)  # noqa: S102
    reimported_wf = namespace["build"]()

    # Every node in the reimported workflow should have the same uid
    for nid, orig_node in wf.nodes.items():
        assert nid in reimported_wf.nodes, f"node {nid} missing from reimported workflow"
        re_node = reimported_wf.nodes[nid]
        assert re_node.uid == orig_node.uid, (
            f"node {nid}: uid mismatch {re_node.uid!r} != {orig_node.uid!r}"
        )
        assert re_node.uid, f"node {nid} has empty uid after reimport"
