from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.porting.workbench import analyze_source
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec


class FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _provider() -> FakeSchemaProvider:
    return FakeSchemaProvider(
        {
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec("STRING", required=True)},
                outputs=[OutputSpec("IMAGE", "image")],
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={"images": InputSpec("IMAGE", required=True), "filename_prefix": InputSpec("STRING", required=True)},
                outputs=[],
            ),
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack=None,
                inputs={"ckpt_name": InputSpec("STRING", required=True)},
                outputs=[OutputSpec("MODEL", "model")],
            ),
            "PromptNode": NodeSchema(
                class_type="PromptNode",
                pack=None,
                inputs={"text": InputSpec("STRING", required=True)},
                outputs=[],
            ),
        }
    )


def _api_workflow() -> dict[str, dict]:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
        "3": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "4": {"class_type": "PromptNode", "inputs": {"widget_0": "hello"}},
    }


def test_analyze_source_reports_raw_json_provenance_assets_schema_and_widget_data(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(_api_workflow()), encoding="utf-8")

    report = analyze_source(str(path), schema_provider=_provider())
    payload = report.to_json()

    assert payload["provenance"]["source_kind"] == "raw_json"
    assert payload["provenance"]["source_path"] == str(path)
    assert payload["source_hash"].startswith("sha256:")
    assert payload["workflow_shape"]["nodes"] == 4
    assert payload["node_counts"]["SaveImage"] == 1
    assert payload["metadata"]["schema_validation"]["schema_provider"] is True
    assert payload["metadata"]["widget_analysis"]["unresolved_widget_aliases"] == []
    assert payload["metadata"]["custom_node_analysis"]["runtime_class_types"] == [
        "CheckpointLoaderSimple",
        "LoadImage",
        "PromptNode",
        "SaveImage",
    ]
    assert [(candidate["name"], candidate["source"]) for candidate in payload["asset_candidates"]] == [
        ("model.safetensors", "api_prompt")
    ]
    codes = [issue["code"] for issue in payload["diagnostics"]]
    assert "filename_only_asset_candidate" in codes
    assert "widget_alias_unresolved" not in codes
    assert "missing_required_input" in codes
    assert "unknown_input" not in codes
    assert any("port convert" in item for item in payload["recommendations"])


def test_analyze_source_reports_widget_schema_that_compile_did_not_apply(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from vibecomfy.porting import widget_schema

    monkeypatch.setitem(widget_schema.WIDGET_SCHEMA, "PromptNode", ["text"])
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(_api_workflow()), encoding="utf-8")

    report = analyze_source(str(path), schema_provider=_provider())
    payload = report.to_json()

    assert payload["metadata"]["widget_analysis"]["missing_compiled_widget_inputs"] == []
    assert "compiled_widget_input_missing" not in [issue["code"] for issue in payload["diagnostics"]]
    assert payload["ok"] is False


def test_analyze_source_rejects_known_runtime_required_inputs_without_schema(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "VHS_VideoCombine",
                    "inputs": {
                        "images": ["2", 0],
                        "frame_rate": 8,
                    },
                },
                "2": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=FakeSchemaProvider({}))
    payload = report.to_json()

    missing = [
        issue
        for issue in payload["diagnostics"]
        if issue["code"] == "known_runtime_required_input_missing"
    ]
    assert {issue["detail"]["input"] for issue in missing} == {
        "filename_prefix",
        "format",
        "loop_count",
        "pingpong",
        "save_output",
    }
    assert payload["ok"] is False


def test_analyze_source_rejects_known_dynamic_combo_without_selector(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "LTXVImgToVideoInplaceKJ",
                    "inputs": {
                        "latent": ["2", 0],
                        "vae": ["3", 0],
                        "num_images.image_1": ["4", 0],
                    },
                },
                "2": {"class_type": "LatentSource", "inputs": {}},
                "3": {"class_type": "VaeSource", "inputs": {}},
                "4": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=FakeSchemaProvider({}))
    payload = report.to_json()

    issue = next(
        issue
        for issue in payload["diagnostics"]
        if issue["code"] == "dynamic_combo_selector_missing"
    )
    assert issue["node_id"] == "1"
    assert issue["detail"]["selector"] == "num_images"
    assert issue["detail"]["dotted_inputs"] == ["num_images.image_1"]
    assert payload["ok"] is False


def test_analyze_source_rejects_sageattention_patch_for_standard_runpod(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "PathchSageAttentionKJ",
                    "inputs": {"model": ["2", 0], "sage_attention": "auto", "allow_compile": False},
                },
                "2": {"class_type": "ModelSource", "inputs": {}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=FakeSchemaProvider({}))
    payload = report.to_json()

    issue = next(
        issue
        for issue in payload["diagnostics"]
        if issue["code"] == "optional_acceleration_requires_unavailable_package"
    )
    assert issue["node_id"] == "1"
    assert issue["detail"]["missing_package"] == "sageattention"
    assert payload["ok"] is False


def test_analyze_source_rejects_ltx_memory_efficient_sage_patch_for_standard_runpod(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "LTX2MemoryEfficientSageAttentionPatch",
                    "inputs": {"model": ["2", 0], "triton_kernels": True},
                },
                "2": {"class_type": "ModelSource", "inputs": {}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=FakeSchemaProvider({}))
    payload = report.to_json()

    issue = next(
        issue
        for issue in payload["diagnostics"]
        if issue["code"] == "optional_acceleration_requires_unavailable_package"
    )
    assert issue["node_id"] == "1"
    assert issue["class_type"] == "LTX2MemoryEfficientSageAttentionPatch"
    assert issue["detail"]["capability"] == "ltx2_memory_efficient_sage_attention"
    assert payload["ok"] is False


def test_analyze_source_rejects_missing_ltx_iclora_runtime_inputs(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "LTXICLoRALoaderModelOnly",
                    "inputs": {"model": ["3", 0], "lora_name": "ltxv/ltx2/control.safetensors"},
                },
                "2": {
                    "class_type": "LTXAddVideoICLoRAGuide",
                    "inputs": {
                        "image": ["4", 0],
                        "latent": ["5", 0],
                        "latent_downscale_factor": ["1", 1],
                        "negative": ["6", 1],
                        "positive": ["6", 0],
                        "vae": ["7", 0],
                    },
                },
                "3": {"class_type": "ModelSource", "inputs": {}},
                "4": {"class_type": "ImageSource", "inputs": {}},
                "5": {"class_type": "LatentSource", "inputs": {}},
                "6": {"class_type": "ConditioningSource", "inputs": {}},
                "7": {"class_type": "VaeSource", "inputs": {}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=FakeSchemaProvider({}))
    payload = report.to_json()
    missing = {
        (issue["class_type"], issue["detail"]["input"])
        for issue in payload["diagnostics"]
        if issue["code"] == "known_runtime_required_input_missing"
    }

    assert ("LTXICLoRALoaderModelOnly", "strength_model") in missing
    for input_name in {"crop", "frame_idx", "strength", "tile_overlap", "tile_size", "use_tiled_encode"}:
        assert ("LTXAddVideoICLoRAGuide", input_name) in missing
    assert payload["ok"] is False


def test_analyze_source_rejects_ltx_preview_override_for_headless_runpod(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "LTX2SamplingPreviewOverride",
                    "inputs": {"model": ["2", 0], "preview_rate": 8},
                },
                "2": {"class_type": "ModelSource", "inputs": {}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=FakeSchemaProvider({}))
    payload = report.to_json()

    issue = next(issue for issue in payload["diagnostics"] if issue["code"] == "headless_preview_override_not_supported")
    assert issue["node_id"] == "1"
    assert issue["class_type"] == "LTX2SamplingPreviewOverride"
    assert issue["detail"]["capability"] == "ltx2_live_sampling_preview"
    assert payload["ok"] is False


def test_analyze_source_rejects_unmaterialized_none_nodes(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
                "2": {"class_type": "None", "inputs": {"UNKNOWN": "missing node"}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=_provider())
    payload = report.to_json()

    assert payload["ok"] is False
    issue = next(issue for issue in payload["diagnostics"] if issue["code"] == "unmaterialized_node_class")
    assert issue["node_id"] == "2"
    assert issue["severity"] == "error"


def test_analyze_source_rejects_opaque_component_nodes(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    component_class = "90db3fa1-b7fd-4c97-90a4-3e9533589dce"
    path.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
                "2": {"class_type": component_class, "inputs": {"image": ["1", 0]}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=_provider())
    payload = report.to_json()

    assert payload["ok"] is False
    issue = next(issue for issue in payload["diagnostics"] if issue["code"] == "opaque_component_node_class")
    assert issue["node_id"] == "2"
    assert issue["class_type"] == component_class


def test_analyze_source_opaque_component_is_warning_in_scratchpad_and_error_in_strict_ready(
    tmp_path: Path,
) -> None:
    path = tmp_path / "opaque_mode.json"
    component_class = "90db3fa1-b7fd-4c97-90a4-3e9533589dce"
    path.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
                "2": {"class_type": component_class, "inputs": {"image": ["1", 0]}},
            }
        ),
        encoding="utf-8",
    )

    scratchpad_report = analyze_source(str(path), schema_provider=_provider(), mode="scratchpad")
    strict_report = analyze_source(str(path), schema_provider=_provider(), mode="strict_ready")

    scratchpad_issue = next(
        issue for issue in scratchpad_report.diagnostics
        if issue.code == "opaque_component_node_class"
    )
    strict_issue = next(
        issue for issue in strict_report.diagnostics
        if issue.code == "opaque_component_node_class"
    )

    assert scratchpad_issue.severity == "warning"
    assert strict_issue.severity == "error"
    assert strict_report.metadata["strict_ready"]["ok"] is False
    assert any(
        issue.code == "strict_ready_missing_public_input"
        for issue in strict_report.diagnostics
    )


def test_analyze_source_resolves_indexed_workflow_references(tmp_path: Path, monkeypatch) -> None:
    workflow_path = tmp_path / "indexed.json"
    workflow = _api_workflow()
    workflow["2"]["inputs"]["filename_prefix"] = "out/indexed"
    workflow["4"]["inputs"] = {"text": "hello"}
    workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "indexed/sample", "path": str(workflow_path)}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    report = analyze_source("indexed/sample", schema_provider=_provider())

    assert report.provenance["source_kind"] == "indexed_json"
    assert report.provenance["indexed_id"] == "indexed/sample"
    assert report.workflow_id == "indexed/sample"
    assert report.metadata["schema_validation"]["ok"] is True


def test_analyze_source_loads_scratchpads_and_reports_helper_diagnostics(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow("scratch", WorkflowSource("scratch"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    workflow.nodes["2"] = VibeNode("2", "GetNode", inputs={"widget_0": "missing_image"})
    workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out/scratch"})
    workflow.edges.append(VibeEdge("2", "0", "3", "images"))
    return workflow
""",
        encoding="utf-8",
    )

    report = analyze_source(str(scratchpad), schema_provider=_provider())

    assert report.provenance["source_kind"] == "scratchpad"
    assert report.workflow_shape["helper_nodes"] == 1
    assert [issue.code for issue in report.diagnostics[:1]] == ["helper_broadcast_unresolved"]
    assert any(issue.detail.get("category") == "schema" for issue in report.diagnostics)


def test_analyze_source_warns_when_scratchpad_save_path_escapes_output_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    output_dir = tmp_path / "configured-output"
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        f"""
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow("scratch", WorkflowSource("scratch"))
    workflow.metadata["comfy_configuration"] = {{"output_directory": {str(output_dir)!r}}}
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={{"filename_prefix": {str(tmp_path / "elsewhere" / "image")!r}}})
    return workflow.finalize_metadata()
""",
        encoding="utf-8",
    )

    report = analyze_source(str(scratchpad), schema_provider=_provider())

    issue = next(issue for issue in report.diagnostics if issue.code == "save_output_path_outside_output_directory")
    assert issue.severity == "warning"
    assert issue.node_id == "1"
    assert issue.detail["field"] == "filename_prefix"
    assert issue.detail["output_directory"] == str(output_dir.resolve())


def test_analyze_source_allows_relative_save_prefix_under_output_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        f"""
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow("scratch", WorkflowSource("scratch"))
    workflow.metadata["comfy_configuration"] = {{"output_directory": {str(tmp_path / "output")!r}}}
    workflow.nodes["1"] = VibeNode("1", "SaveVideo", widgets={{"widget_0": "video/ComfyUI"}})
    return workflow.finalize_metadata()
""",
        encoding="utf-8",
    )

    report = analyze_source(str(scratchpad), schema_provider=_provider())

    assert "save_output_path_outside_output_directory" not in [issue.code for issue in report.diagnostics]


def test_analyze_source_loads_ready_ids() -> None:
    report = analyze_source("image/z_image")

    assert report.provenance["source_kind"] == "ready"
    assert report.provenance["indexed_id"] == "image/z_image"
    assert report.workflow_id == "image/z_image"
    assert report.source_hash is not None


def test_analyze_source_covers_simple_template_and_wan_animate_target() -> None:
    simple = analyze_source("image/z_image").to_json()
    wan = analyze_source("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai").to_json()

    assert simple["ok"] is True
    assert simple["provenance"]["source_kind"] == "ready"
    assert simple["workflow_id"] == "image/z_image"
    assert simple["workflow_shape"]["helper_nodes"] == 0
    assert "source_hash" in simple
    assert any("port convert" in item for item in simple["recommendations"])

    assert wan["ok"] is False
    assert wan["provenance"]["source_kind"] == "ready"
    assert wan["workflow_id"] == "video/wanvideo_wrapper_22_wan_animate_preprocess_kijai"
    assert wan["workflow_shape"]["runtime_nodes"] > 0
    assert wan["workflow_shape"]["helper_nodes"] > 0
    assert any(item["code"] == "known_runtime_required_input_missing" for item in wan["diagnostics"])
    assert "ComfyUI-WanAnimatePreprocess" in {pack["pack_name"] for pack in wan["node_pack_suggestions"]}
    assert "ComfyUI-WanVideoWrapper" in {pack["pack_name"] for pack in wan["node_pack_suggestions"]}
    assert "helper_broadcast_resolved" in {issue["code"] for issue in wan["diagnostics"]}
    assert all(
        issue["class_type"] not in {"Note", "MarkdownNote", "SetNode", "GetNode"}
        for issue in wan["diagnostics"]
        if issue["code"] == "unresolved_runtime_class"
    )


def test_analyze_source_infers_node_packs_from_runtime_classes_only(tmp_path: Path) -> None:
    path = tmp_path / "custom_nodes.json"
    path.write_text(
        json.dumps(
            {
                "1": {"class_type": "Note", "inputs": {"widget_0": "UI note"}},
                "2": {"class_type": "WanVideoSampler", "inputs": {}},
                "3": {"class_type": "UnknownRuntimeNode", "inputs": {}},
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(str(path), schema_provider=FakeSchemaProvider({}))
    payload = report.to_json()

    assert payload["metadata"]["custom_node_analysis"]["helper_class_types_excluded"] == ["Note"]
    assert payload["metadata"]["custom_node_analysis"]["missing_runtime_class_types"] == [
        "UnknownRuntimeNode",
        "WanVideoSampler",
    ]
    assert [(pack["pack_name"], pack["matched_classes"], pack["pip_packages"]) for pack in payload["node_pack_suggestions"]] == [
        ("ComfyUI-WanVideoWrapper", ["WanVideoSampler"], ["onnx", "opencv-python-headless"])
    ]
    custom_node_errors = [
        issue for issue in payload["diagnostics"] if issue["code"] == "unresolved_runtime_class"
    ]
    expected_message = "unknown class: UnknownRuntimeNode. Run 'nodes lookup UnknownRuntimeNode' to find the providing pack, then 'nodes install <slug>'."
    assert custom_node_errors == [
        {
            "code": "unresolved_runtime_class",
            "message": expected_message,
            "severity": "error",
            "node_id": None,
            "class_type": "UnknownRuntimeNode",
            "detail": {"category": "custom_nodes", "runtime_class_type": "UnknownRuntimeNode"},
            "recommendation": expected_message,
        }
    ]


def test_analyze_source_can_include_opt_in_model_head_checks(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "UNETLoader",
                        "properties": {
                            "models": [
                                {"name": "model.safetensors", "url": "https://example.test/model.safetensors"}
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = analyze_source(
        str(path),
        head_check_models=True,
        head_client=lambda url, timeout: {"status_code": 403, "url": url},
    )

    assert [(check.url, check.ok, check.status_code, check.error) for check in report.asset_checks] == [
        ("https://example.test/model.safetensors", False, 403, "license_gated_or_forbidden")
    ]
    assert "model_asset_head_check_failed" in [issue.code for issue in report.diagnostics]


# ---------------------------------------------------------------------------
# T5: style diagnostics in port check
# ---------------------------------------------------------------------------


def test_port_check_detects_local_helper_copy_in_strict_template(tmp_path: Path) -> None:
    """local_helper_copy_in_strict_template warning for ready template with def _node."""
    from vibecomfy.porting.emitter import READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE
    from vibecomfy.porting.workbench import LoadedPortSource, _strict_template_style_diagnostics
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    # Create a ready template file with def _node
    template_content = '''\
# vibecomfy: generated
READY_METADATA = {"ready_template": "image/test_local_helper", "source_workflow": "test.json", "source_role": "source"}
READY_REQUIREMENTS = {"models": [], "custom_nodes": []}

def build():
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource
    wf = VibeWorkflow("image/test_local_helper", WorkflowSource("image/test_local_helper"))
    node = wf.node("LoadImage", image="test.png")
    wf.finalize_metadata()
    return wf

def _node(wf, class_type, _id, _extras=None, _outputs=None, **kwargs):
    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            builder.node.inputs[key] = value
    return builder
'''
    template_path = tmp_path / "test_local_helper.py"
    template_path.write_text(template_content, encoding="utf-8")

    # Build a LoadedPortSource with source_kind="ready" and the file path
    loaded = LoadedPortSource(
        source_ref="image/test_local_helper",
        source_kind="ready",
        workflow=VibeWorkflow("image/test_local_helper", WorkflowSource("image/test_local_helper")),
        source_path=str(template_path),
        indexed_id="image/test_local_helper",
    )

    issues = _strict_template_style_diagnostics(loaded)

    local_helper_codes = [
        issue.code for issue in issues
        if issue.code == READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE
    ]
    assert len(local_helper_codes) > 0, (
        f"Expected local_helper_copy_in_strict_template diagnostic, "
        f"got codes: {[issue.code for issue in issues]}"
    )


def test_port_check_no_false_positive_for_non_ready_source(tmp_path: Path) -> None:
    """No local_helper_copy_in_strict_template for scratchpad sources."""
    from vibecomfy.porting.emitter import READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE
    from vibecomfy.porting.workbench import LoadedPortSource, _strict_template_style_diagnostics
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    # Even with _node in the source, scratchpad kind should not trigger the diagnostic
    loaded = LoadedPortSource(
        source_ref="test_scratchpad",
        source_kind="scratchpad",
        workflow=VibeWorkflow("test_scratchpad", WorkflowSource("test_scratchpad")),
        source_path="/nonexistent/path.py",
    )

    issues = _strict_template_style_diagnostics(loaded)
    assert len(issues) == 0, f"Should not flag for scratchpad sources"


# ---------------------------------------------------------------------------
# T14 (M2 Step 11): PNG/WebP embedded-workflow ingest
# ---------------------------------------------------------------------------


def _png_with_workflow(path: Path, chunk: str | None, key: str = "workflow") -> Path:
    # Building the PNG fixture needs Pillow (the optional ``[png]`` extra). Skip
    # rather than fail when it is absent — matching the optional-dependency test
    # convention. (``test_load_port_source_png_without_pillow_raises`` still needs
    # PIL here to create the fixture before monkeypatching it away.)
    import pytest

    pytest.importorskip("PIL")
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    if chunk is not None:
        info.add_text(key, chunk)
    Image.new("RGB", (4, 4), (0, 0, 0)).save(path, "PNG", pnginfo=info)
    return path


def test_load_port_source_png_ingests_same_as_json(tmp_path: Path) -> None:
    from vibecomfy.porting.workbench import load_port_source

    workflow_json = json.dumps(_api_workflow())

    json_path = tmp_path / "flat.json"
    json_path.write_text(workflow_json, encoding="utf-8")
    png_path = _png_with_workflow(tmp_path / "flat.png", workflow_json)

    from_json = load_port_source(str(json_path), schema_provider=_provider())
    from_png = load_port_source(str(png_path), schema_provider=_provider())

    assert set(from_png.workflow.nodes) == set(from_json.workflow.nodes)
    assert {n.class_type for n in from_png.workflow.nodes.values()} == {
        n.class_type for n in from_json.workflow.nodes.values()
    }
    assert from_png.raw_workflow == from_json.raw_workflow


def test_load_port_source_png_prompt_fallback(tmp_path: Path) -> None:
    from vibecomfy.porting.workbench import load_port_source

    png_path = _png_with_workflow(
        tmp_path / "p.png", json.dumps(_api_workflow()), key="prompt"
    )
    loaded = load_port_source(str(png_path), schema_provider=_provider())
    assert len(loaded.workflow.nodes) == 4


def test_load_port_source_png_missing_chunk_raises(tmp_path: Path) -> None:
    import pytest

    from vibecomfy.porting.workbench import load_port_source

    png_path = _png_with_workflow(tmp_path / "empty.png", None)
    with pytest.raises(ValueError, match="No embedded ComfyUI workflow"):
        load_port_source(str(png_path), schema_provider=_provider())


def test_load_port_source_png_without_pillow_raises(tmp_path: Path, monkeypatch) -> None:
    import sys

    import pytest

    from vibecomfy.porting.workbench import load_port_source

    png_path = _png_with_workflow(tmp_path / "x.png", json.dumps(_api_workflow()))
    # Force `from PIL import Image` to fail inside _load_workflow_from_image.
    monkeypatch.setitem(sys.modules, "PIL", None)
    with pytest.raises(ImportError, match="Pillow"):
        load_port_source(str(png_path), schema_provider=_provider())
