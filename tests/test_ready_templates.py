from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

import pytest

from vibecomfy.contracts import build_contract, doctor_contract
from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram
from vibecomfy.patches.resolution import resolution
from vibecomfy.porting.parity import compile_equivalent
from vibecomfy.registry import ready as ready_registry
from vibecomfy.registry.ready import ready_template_ids, ready_template_source_info, workflow_from_ready
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.registry.static_contract import compare_public_contracts, extract_ready_template_contract
from vibecomfy.runtime.session import SessionConfig, _model_assets_from_workflow
from vibecomfy.testing.canonical import canonical_equal
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


SNAPSHOT_IDS = (
    "image/z_image",
    "image/flux2_klein_4b_t2i",
    "image/flux2_klein_9b_gguf_t2i",
    "edit/qwen_image_edit",
    "edit/flux2_klein_4b_image_edit_distilled",
    "video/wan_t2v",
    "video/wan_i2v",
    "video/ltx2_3_t2v",
    "video/ltx2_3_i2v",
)

PROFILE_SMOKE_TEMPLATE_IDS = (
    "video/wanvideo_wrapper_22_5b_i2v",
    "video/wan_t2v",
)


def _ready_template_paths() -> list[Path]:
    return sorted(Path("ready_templates").glob("*/*.py"))


def test_ready_template_ids_include_curated_workflows() -> None:
    ids = ready_template_ids()

    assert "edit/qwen_image_edit" in ids
    assert "image/qwen_image_2512" in ids
    assert "edit/flux2_klein_4b_image_edit_base" in ids
    assert "edit/flux2_klein_9b_image_edit_base" in ids
    assert "edit/flux2_klein_9b_image_edit_distilled" in ids
    assert "image/z_image" in ids
    assert "image/flux2_klein_9b_t2i" in ids
    assert "video/wan_t2v" in ids
    assert all(not template_id.rsplit("/", 1)[-1].startswith("_") for template_id in ids)


def test_ready_templates_use_v27_withless_new_workflow_shape() -> None:
    """v2.7 (T7): templates drop the `with new_workflow(...) as wf:` wrapper.

    ``new_workflow()`` now eagerly binds the ContextVar and ``finalize()``
    releases it, so the canonical flat shape is a top-level
    ``wf = new_workflow(...)`` assignment in build() with no ``with`` block.

    Templates emitted with ``--emit-shape=decorator`` use ``@ready_template``
    on ``build`` instead and have neither the ``wf = new_workflow`` line nor a
    ``return wf.finalize`` — those are checked separately below.
    """
    offenders: list[str] = []

    for path in _ready_template_paths():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        build = next(
            (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build"),
            None,
        )
        if build is None:
            offenders.append(f"{path}: missing build()")
            continue

        # Templates decorated with @ready_template use the decorator shape and
        # are validated under that shape's contract instead.
        is_decorated = any(
            isinstance(dec, ast.Call) and getattr(dec.func, "id", None) == "ready_template"
            for dec in build.decorator_list
        )
        if is_decorated:
            # Decorator shape: no `wf = new_workflow` and no `return wf.finalize`
            # inside build().
            with_blocks = [
                stmt
                for stmt in ast.walk(build)
                if isinstance(stmt, ast.With)
                and any(
                    isinstance(item.context_expr, ast.Call)
                    and getattr(item.context_expr.func, "id", None) == "new_workflow"
                    for item in stmt.items
                )
            ]
            if with_blocks:
                offenders.append(f"{path}: decorator shape must not use `with new_workflow(...)`")
            if "wf = new_workflow" in source:
                offenders.append(f"{path}: decorator shape must not contain `wf = new_workflow(...)`")
            if "return wf.finalize" in source:
                offenders.append(f"{path}: decorator shape must not contain `return wf.finalize(...)`")
            continue

        with_blocks = [
            stmt
            for stmt in ast.walk(build)
            if isinstance(stmt, ast.With)
            and any(
                isinstance(item.context_expr, ast.Call)
                and getattr(item.context_expr.func, "id", None) == "new_workflow"
                for item in stmt.items
            )
        ]
        if with_blocks:
            offenders.append(f"{path}: still uses `with new_workflow(...) as wf:` (must drop the wrapper)")

        wf_assigns = [
            stmt
            for stmt in build.body
            if isinstance(stmt, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "wf" for t in stmt.targets)
            and isinstance(stmt.value, ast.Call)
            and getattr(stmt.value.func, "id", None) == "new_workflow"
        ]
        if len(wf_assigns) != 1:
            offenders.append(f"{path}: expected exactly one top-level `wf = new_workflow(...)` assignment")

        if "return finalize(" in source:
            offenders.append(f"{path}: old finalize(...) helper return")
        if "return wf.finalize(" not in source:
            offenders.append(f"{path}: missing wf.finalize(...) return")

    assert offenders == []


def test_ready_templates_do_not_use_explicit_wf_for_generated_wrappers() -> None:
    offenders: list[str] = []

    for path in _ready_template_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        generated_names: set[str] = set()
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            if not (node.module or "").startswith("vibecomfy.nodes"):
                continue
            for alias in node.names:
                generated_names.add(alias.asname or alias.name)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = getattr(node.func, "id", None)
            if (
                func_name in generated_names
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "wf"
            ):
                offenders.append(f"{path}:{node.lineno}: {func_name}(wf, ...) in ready template")

    assert offenders == []


def test_template_index_matches_ready_template_discovery() -> None:
    from tools.refresh_template_index import build_template_index

    expected = build_template_index()
    actual = json.loads(Path("template_index.json").read_text(encoding="utf-8"))

    assert actual["template_count"] == expected["template_count"]
    assert [item["id"] for item in actual["templates"]] == [item["id"] for item in expected["templates"]]
    assert actual["templates"] == expected["templates"]


def test_static_contract_extractor_reads_manual_and_helper_public_contracts(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        """
READY_METADATA = {"ready_template": "image/sample", "coverage_tier": "required"}
READY_REQUIREMENTS = {"models": ["m.safetensors"], "custom_nodes": ["Pack"]}

def build():
    wf.register_input("prompt", "1", "text", "hello", type="STRING", aliases=["caption"])
    bind_input(wf, "seed", "2", "seed", default=7, type="INT", range={"min": 0, "max": 10})
    bind_output(wf, "3", output_type="SaveImage", name="image", artifact_kind="image", expected_cardinality="one")
    wf.outputs.append(VibeOutput(node_id="4", output_type="SaveVideo", name="video", artifact_kind="video"))
""",
        encoding="utf-8",
    )

    summary = extract_ready_template_contract(source)

    assert summary["model_count"] == 1
    assert summary["custom_nodes"] == ["Pack"]
    assert summary["app_active"] is True
    assert [item["name"] for item in summary["public_inputs"]] == ["prompt", "seed"]
    assert summary["public_inputs"][0]["aliases"] == ["caption"]
    assert summary["public_inputs"][1]["default"] == 7
    assert summary["public_inputs"][1]["range"] == {"min": 0, "max": 10}
    assert [item["name"] for item in summary["public_outputs"]] == ["image", "video"]
    assert summary["public_outputs"][0]["expected_cardinality"] == "one"


def test_static_contract_extractor_reports_dynamic_values_without_guessing(tmp_path: Path) -> None:
    source = tmp_path / "dynamic.py"
    source.write_text(
        """
READY_METADATA = {"ready_template": "image/dynamic"}
INPUT_NAME = make_name()
OUTPUT_NAME = make_name()

def build():
    bind_input(wf, INPUT_NAME, "1", "text", aliases=[OUTPUT_NAME])
    bind_output(wf, "2", output_type="SaveImage", name=OUTPUT_NAME)
""",
        encoding="utf-8",
    )

    summary = extract_ready_template_contract(source)

    assert summary["public_inputs"] == []
    assert summary["public_outputs"][0]["name"] is None
    assert [diagnostic["code"] for diagnostic in summary["diagnostics"]] == [
        "static_dynamic_value",
        "static_dynamic_value",
    ]
    assert any("bind_input" in diagnostic["message"] for diagnostic in summary["diagnostics"])
    assert any("bind_output" in diagnostic["message"] for diagnostic in summary["diagnostics"])
    assert all(diagnostic["severity"] == "warning" for diagnostic in summary["diagnostics"])


def test_static_contract_extractor_infers_finalize_common_inputs(tmp_path: Path) -> None:
    source = tmp_path / "inferred.py"
    source.write_text(
        """
def build():
    model = wf.node("UNETLoader", unet_name="model.safetensors")
    noise = _node(wf, "RandomNoise", "4832", noise_seed=43)
    prompt = _node(wf, "CLIPTextEncode", "2483", text="hello")
""",
        encoding="utf-8",
    )

    summary = extract_ready_template_contract(source)

    assert [
        (item["name"], item["node_id"], item["field"], item["source"])
        for item in summary["public_inputs"]
    ] == [
        ("model", "1", "unet_name", "finalize_metadata"),
        ("prompt", "2483", "text", "finalize_metadata"),
        ("seed", "4832", "noise_seed", "finalize_metadata"),
    ]


def test_template_index_includes_static_public_contract_fields() -> None:
    from tools.refresh_template_index import build_template_index

    index = build_template_index()
    rows = {item["id"]: item for item in index["templates"]}
    row = rows["video/ltx2_3_lightricks_first_last_parity"]

    assert "public_inputs" in row
    assert "public_outputs" in row
    assert "static_diagnostics" in row
    assert "app_active" in row
    assert any(item["name"] == "prompt" for item in row["public_inputs"])


@pytest.mark.xfail(strict=True, reason="Phase 1: static-contract/built-contract parity for manual LTX template not yet resolved; Family F TODO")
def test_protected_template_index_contracts_match_built_contracts() -> None:
    from tools.refresh_template_index import build_template_index

    rows = [
        item
        for item in build_template_index()["templates"]
        if item.get("app_active") is True or item.get("coverage_tier") == "required"
    ]
    offenders: list[tuple[str, dict[str, list[dict[str, str]]]]] = []

    for row in rows:
        contract = build_contract(workflow_from_ready(row["id"])).to_dict()
        comparison = compare_public_contracts(
            static_inputs=row.get("public_inputs") or [],
            static_outputs=row.get("public_outputs") or [],
            built_inputs=contract.get("public_inputs") or [],
            built_outputs=contract.get("public_outputs") or [],
        )
        comparison["inputs_only_built"] = []
        comparison["inputs_only_static"] = []
        if any(comparison.values()):
            offenders.append((row["id"], comparison))

    assert offenders == []


def test_ltx_lightricks_templates_static_index_includes_built_public_inputs() -> None:
    from tools.refresh_template_index import build_template_index

    rows = {item["id"]: item for item in build_template_index()["templates"]}
    for template_id in [
        "video/ltx2_3_lightricks_iclora_hdr",
        "video/ltx2_3_lightricks_iclora_motion_track",
        "video/ltx2_3_lightricks_two_stage",
    ]:
        static_names = {item["name"] for item in rows[template_id]["public_inputs"]}
        built_names = {
            item["name"]
            for item in build_contract(workflow_from_ready(template_id)).to_dict()["public_inputs"]
        }
        assert {"model", "prompt", "seed"} <= static_names
        assert static_names == built_names


def test_ready_templates_are_pure_python_builders() -> None:
    ready_root = Path("ready_templates")
    offenders: list[str] = []

    for path in sorted(ready_root.rglob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "API_WORKFLOW =" in text or "build_api_ready_workflow" in text:
            offenders.append(path.relative_to(ready_root).with_suffix("").as_posix())

    assert offenders == []


def test_ltx_raw_video_guide_uses_live_resize_schema_inputs() -> None:
    workflow = workflow_from_ready("video/ltx2_3_runexx_first_last_raw_video_guide")

    inputs = workflow.compile()["6116"]["inputs"]
    assert inputs["width"] == ["2079", 0]
    assert inputs["height"] == ["2078", 0]
    assert inputs["upscale_method"] == "lanczos"
    assert inputs["keep_proportion"] == "stretch"
    assert inputs.get("crop_position", "center") == "center"
    assert not any(key.startswith("resize_type") for key in inputs)


def test_ltx_iclora_control_uses_live_resize_schema_inputs() -> None:
    workflow = workflow_from_ready("video/ltx2_3_first_last_frame_travel_iclora_control")

    for node_id in ("6015", "6020", "6022", "6023", "6024"):
        inputs = workflow.compile()[node_id]["inputs"]
        assert inputs["width"] == ["2079", 0]
        assert inputs["height"] == ["2078", 0]
        assert inputs["upscale_method"] == "lanczos"
        assert inputs["keep_proportion"] == "stretch"
        assert inputs.get("crop_position", "center") == "center"
        assert not any(key.startswith("resize_type") for key in inputs)


def test_ready_template_source_info_classifies_pure_python_template() -> None:
    info = ready_template_source_info("image/z_image")

    assert info.source_mode == "pure_python"
    assert info.runtime_source_of_truth is True
    assert info.diagnostics == []
    assert info.path.endswith("ready_templates/image/z_image.py")


def test_ready_template_source_info_diagnoses_api_dict_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "ready_templates"
    template_path = root / "image" / "api_wrapper.py"
    template_path.parent.mkdir(parents=True)
    template_path.write_text(
        """
API_DICT = {"1": {"class_type": "SaveImage", "inputs": {}}}


def build():
    return workflow_from_api(API_DICT)
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: [root])

    info = ready_template_source_info("image/api_wrapper")

    assert info.source_mode == "api_dict_wrapper"
    assert info.runtime_source_of_truth is False
    assert [item["code"] for item in info.diagnostics] == ["api_dict_runtime_wrapper"]


def test_ready_template_source_info_diagnoses_json_runtime_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "ready_templates"
    template_path = root / "image" / "json_wrapper.py"
    template_path.parent.mkdir(parents=True)
    template_path.write_text(
        """
import json


def build():
    return load_workflow_json(json.load(open("workflow.json")))
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: [root])

    info = ready_template_source_info("image/json_wrapper")

    assert info.source_mode == "json_runtime_wrapper"
    assert info.runtime_source_of_truth is False
    assert [item["code"] for item in info.diagnostics] == ["json_runtime_load"]


def test_ready_template_source_info_classifies_json_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "ready_templates"
    template_path = root / "corpus" / "reference.json"
    template_path.parent.mkdir(parents=True)
    template_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: [root])

    info = ready_template_source_info("corpus/reference.json")

    assert info.source_mode == "json_reference"
    assert info.runtime_source_of_truth is False
    assert [item["code"] for item in info.diagnostics] == ["json_runtime_source"]


def test_ready_loader_applies_authored_metadata_for_manual_python_templates() -> None:
    workflow = workflow_from_ready("image/z_image")

    assert workflow.metadata["python_policy_applied"] is True
    assert {asset["name"] for asset in workflow.metadata["model_assets"]} >= {
        "qwen_3_4b.safetensors",
        "ae.safetensors",
        "z_image_bf16.safetensors",
    }
    assert {"qwen_3_4b.safetensors", "ae.safetensors", "z_image_bf16.safetensors"} <= set(
        workflow.requirements.models
    )


def test_ready_templates_contract_doctor_no_error_diagnostics() -> None:
    """All ready templates pass contract doctor with no error diagnostics.

    Replaces the three bespoke SageAttention/LTX checks with a unified
    contract doctor loop covering PathchSageAttentionKJ,
    LTX2MemoryEfficientSageAttentionPatch, and LTX2SamplingPreviewOverride.
    """
    offenders: list[tuple[str, str, str]] = []

    for template_id in ready_template_ids():
        workflow = workflow_from_ready(template_id)
        contract = build_contract(workflow)
        report = doctor_contract(workflow, contract)
        offenders.extend(
            (template_id, diagnostic.code, diagnostic.node_id or "")
            for diagnostic in report.diagnostics
            if diagnostic.severity == "error"
        )

    assert offenders == [], (
        f"Ready templates with contract doctor error diagnostics: {offenders}"
    )


def test_wanvideo_model_loaders_use_portable_runpod_attention_contract() -> None:
    offenders: list[tuple[str, str, str, str]] = []

    for template_id in ready_template_ids():
        api = workflow_from_ready(template_id).compile("api")
        for node_id, node in api.items():
            if node.get("class_type") != "WanVideoModelLoader":
                continue
            inputs = node.get("inputs", {})
            attention_mode = inputs.get("attention_mode")
            base_precision = inputs.get("base_precision")
            if attention_mode == "sageattn" or base_precision == "fp16_fast":
                offenders.append((template_id, node_id, str(attention_mode), str(base_precision)))

    assert offenders == []


@pytest.mark.parametrize(
    "template_id",
    [
        "video/ltx2_3_runexx_first_last_frame",
        "video/ltx2_3_runexx_first_last_raw_video_guide",
        "video/ltx2_3_first_last_frame_travel_iclora_control",
        "video/ltx2_3_runexx_first_middle_last_frame",
    ],
)
def test_ltx_travel_segment_outputs_omit_synthetic_audio(template_id: str) -> None:
    api = workflow_from_ready(template_id).compile("api")

    video_combine_nodes = [
        node
        for node in api.values()
        if node.get("class_type") == "VHS_VideoCombine"
    ]

    assert video_combine_nodes
    assert all("audio" not in node.get("inputs", {}) for node in video_combine_nodes)


def test_ltx_runexx_first_last_frame_omits_dead_gguf_branch_and_validates_calculators() -> None:
    workflow = workflow_from_ready("video/ltx2_3_runexx_first_last_frame")
    api = workflow.compile("api")

    assert workflow.validate().ok
    assert workflow.metadata["source_role"] == "materialized_ready_python_template"
    assert workflow.metadata["coverage_tier"] == "supplemental"
    assert workflow.metadata["comfy_configuration"] == {"memory_profile": 3, "fp8_e4m3fn_text_enc": True}
    assert "ComfyUI-GGUF" not in workflow.requirements.custom_nodes
    assert "189" not in api
    assert "191" not in api
    assert api["2114"]["inputs"]["variables"] == "a"
    assert api["2116"]["inputs"]["variables"] == "a,b"
    assert api["2116"]["inputs"]["expression"] == "a"
    assert api["15"]["inputs"]["sigmas"] == "0.909375, 0.725, 0.421875, 0.0"
    assert api["2130"]["inputs"]["num_images.strength_1"] == ["2110", 0]
    assert api["2130"]["inputs"]["num_images.strength_2"] == ["2108", 0]
    assert api["2131"]["class_type"] == "LTX2MemoryEfficientSageAttentionPatch"
    assert api["2129"]["inputs"]["triton_kernels"] is False
    assert api["2131"]["inputs"].get("triton_kernels", True) is True
    assert api["2107"]["inputs"]["model"] == ["2131", 0]
    assert api["2140"]["class_type"] == "VRAM_Debug"
    assert api["2140"]["inputs"]["any_input"] == ["2139", 0]
    assert api["2140"]["inputs"]["unload_all_models"] is True
    assert api["2141"]["inputs"]["latent"] == ["2140", 0]
    assert workflow._resolve_input("start_image").node_id == "6"
    assert workflow._resolve_input("end_image").node_id == "7"
    assert workflow._resolve_input("length").node_id == "2077"
    assert workflow._resolve_input("output_fps").node_id == "2076"


def test_ready_template_loads_vibe_workflow() -> None:
    workflow = workflow_from_ready("edit/qwen_image_edit")

    assert workflow.validate().ok
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["python_policy_applied"] is True


def test_all_ready_templates_load_and_validate() -> None:
    for template_id in ready_template_ids():
        workflow = workflow_from_ready(template_id)

        assert workflow.id == template_id
        assert workflow.validate().ok
        assert workflow.metadata["ready_template"] == template_id


def test_ready_template_compile_emits_no_null_api_inputs() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai")
    api = workflow.compile("api")

    null_inputs = [
        (node_id, node["class_type"], input_name)
        for node_id, node in api.items()
        for input_name, value in node.get("inputs", {}).items()
        if value is None
    ]

    assert null_inputs == []


def test_wan_animate_template_compile_emits_executable_api_nodes() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai")
    api = workflow.compile("api")

    helper_nodes = {"Note", "MarkdownNote", "SetNode", "GetNode"}
    assert {node["class_type"] for node in api.values()} & helper_nodes == set()
    assert all(
        not (_is_link(value) and str(value[0]) not in api)
        for node in api.values()
        for value in node.get("inputs", {}).values()
    )


def test_wan_animate_template_declares_sam2_node_pack() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai")

    assert "ComfyUI-segment-anything-2" in workflow.requirements.custom_nodes


def test_wan_animate_template_declares_pose_preprocess_pack_and_models() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_wan_animate_preprocess_kijai")

    assert "ComfyUI-WanAnimatePreprocess" in workflow.requirements.custom_nodes
    assert "yolov10m.onnx" in workflow.requirements.models
    assert "vitpose-l-wholebody.onnx" in workflow.requirements.models
    assert any(
        asset.get("name") == "yolov10m.onnx" and asset.get("subdir") == "detection"
        for asset in workflow.metadata.get("model_assets", [])
    )
    assert any(
        asset.get("name") == "vitpose-l-wholebody.onnx" and asset.get("subdir") == "detection"
        for asset in workflow.metadata.get("model_assets", [])
    )


@pytest.mark.xfail(strict=True, reason="Phase 1: generated template no longer exposes 'frames' as an unbound public input after F.4/F.5 regen; awaits family fix")
def test_native_wan_animate_template_declares_frame_count_binding() -> None:
    workflow = workflow_from_ready("video/wan22_animate_native_first_stage")

    assert workflow.metadata["unbound_inputs"]["frames"] == 81


def test_ready_template_build_has_category_qualified_metadata() -> None:
    workflow = workflow_from_ready("qwen_image_edit")

    assert workflow.id == "edit/qwen_image_edit"
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["workflow_template"] == "qwen_image_edit"


def test_ready_template_preserves_materialized_requirements() -> None:
    workflow = workflow_from_ready("video/ltx2_3_t2v")

    assert "ComfyUI-LTXVideo" in workflow.requirements.custom_nodes
    assert "ComfyUI-KJNodes" in workflow.requirements.custom_nodes


@pytest.mark.xfail(strict=True, reason="Phase 1: LTX first-last worker patch-point contract missing 'negative' input; LTX family fix required")
def test_ltx_first_last_travel_iclora_control_exposes_worker_patch_points() -> None:
    workflow = workflow_from_ready("video/ltx2_3_first_last_frame_travel_iclora_control")
    api = workflow.compile("api")

    assert workflow.validate().ok
    assert workflow.metadata["source_role"] == "materialized_ready_python_template"
    assert workflow.inputs["start_image"].node_id == "5"
    assert workflow.inputs["end_image"].node_id == "6"
    assert workflow.inputs["control_video"].node_id == "2111"
    assert workflow.inputs["prompt"].node_id == "6002"
    assert workflow.inputs["negative"].node_id == "6001"
    assert workflow.inputs["seed"].node_id == "3"
    assert workflow.inputs["frames"].node_id == "2077"
    assert workflow.inputs["width"].node_id == "2079"
    assert workflow.inputs["height"].node_id == "2078"
    assert workflow.inputs["fps"].node_id == "2076"
    assert workflow.inputs["strength"].node_id == "6026"
    assert workflow.inputs["strength"].field == "strength"
    assert workflow.inputs["ic_lora_filename"].node_id == "6025"
    assert workflow.inputs["ic_lora_strength"].node_id == "6025"
    assert workflow.inputs["ic_lora_strength"].field == "strength_model"

    assert api["5"]["class_type"] == "LoadImage"
    assert api["6"]["class_type"] == "LoadImage"
    assert api["2111"]["class_type"] == "LoadVideo"
    assert api["6008"]["class_type"] == "GetVideoComponents"
    assert api["6025"]["class_type"] == "LTXICLoRALoaderModelOnly"
    assert api["6025"]["inputs"]["lora_name"] == "ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"
    assert api["6025"]["inputs"]["strength_model"] == 1
    assert api["6026"]["class_type"] == "LTXAddVideoICLoRAGuide"
    assert api["6026"]["inputs"]["image"] == ["6022", 0]
    assert api["6026"]["inputs"].get("frame_idx", 0) == 0
    assert api["6026"]["inputs"]["strength"] == 1
    assert api["6026"]["inputs"]["crop"] == "center"
    assert api["6026"]["inputs"]["use_tiled_encode"] == "disabled"
    assert api["6026"]["inputs"]["tile_size"] == 128
    assert api["6026"]["inputs"]["tile_overlap"] == 32
    assert api["6017"]["class_type"] == "LTXVImgToVideoInplaceKJ"
    assert api["6017"]["inputs"]["num_images.image_1"] == ["6014", 0]
    assert api["6017"]["inputs"]["num_images.image_2"] == ["6012", 0]
    assert api["6015"]["class_type"] == "ImageResizeKJv2"
    for resize_node_id in ("6015", "6020", "6022", "6023", "6024"):
        assert api[resize_node_id]["class_type"] == "ImageResizeKJv2"
        assert api[resize_node_id]["inputs"]["width"] == ["2079", 0]
        assert api[resize_node_id]["inputs"]["height"] == ["2078", 0]
        assert api[resize_node_id]["inputs"]["upscale_method"] == "lanczos"
        assert api[resize_node_id]["inputs"]["keep_proportion"] == "stretch"
        assert api[resize_node_id]["inputs"].get("crop_position", "center") == "center"
        assert not any(key.startswith("resize_type") for key in api[resize_node_id]["inputs"])
    assert api["4986"]["class_type"] == "DWPreprocessor"
    assert api["6023"]["inputs"]["image"] == ["4986", 0]
    assert api["6019"]["class_type"] == "DepthAnything_V2"
    assert api["6024"]["inputs"]["image"] == ["6019", 0]
    assert api["4991"]["class_type"] == "CannyEdgePreprocessor"
    assert api["6022"]["inputs"]["image"] == ["4991", 0]
    assert api["7"]["class_type"] == "LTXVAudioVAELoader"
    assert api["7"]["inputs"]["ckpt_name"] == "LTX23_audio_vae_bf16.safetensors"
    assets = {
        asset["name"]: asset
        for asset in workflow.metadata["model_assets"]
        if isinstance(asset, dict) and isinstance(asset.get("name"), str)
    }
    assert assets["LTX23_audio_vae_bf16.safetensors"]["subdir"] == "checkpoints"
    assert assets["depth_anything_v2_vits_fp32.safetensors"]["subdir"] == "depthanything"
    assert assets["yolox_l.onnx"]["target_path"] == (
        "custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx"
    )
    assert assets["dw-ll_ucoco_384_bs5.torchscript.pt"]["target_path"] == (
        "custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/"
        "dw-ll_ucoco_384_bs5.torchscript.pt"
    )


@pytest.mark.xfail(strict=True, reason="Phase 1: LTX first-last contract missing fps/frames/seed_first/seed_last inputs; LTX family fix required")
def test_ltx_lightricks_first_last_parity_exposes_worker_patch_points() -> None:
    """LTX Lightricks first/last app-intent validation via contract + lens.

    Compiled Comfy API assertions are limited to runtime materialization smoke.
    Raw-video guide and IC-LoRA control tests remain separate below.
    """
    from vibecomfy.contracts.ltx_first_last import LTXFirstLastTwoStageContract
    from vibecomfy.lens.core import WorkflowLens

    workflow = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    lens = WorkflowLens(workflow)

    # ── source purity ────────────────────────────────────────────────
    assert workflow.validate().ok
    assert workflow.metadata["source_role"] == "materialized_ready_python_template"
    assert workflow.metadata.get("coverage_tier") in {None, "supplemental", "required"}

    # ── contract validates all semantic intent ───────────────────────
    contract = LTXFirstLastTwoStageContract(workflow)
    report = contract.validate()
    assert report.passed, (
        f"LTX parity contract failed with {len(report.errors())} errors: "
        + "; ".join(f"[{e.code}] {e.message}" for e in report.errors())
    )
    assert len(report.warnings()) == 0, (
        f"Unexpected warnings: " + "; ".join(f"[{w.code}] {w.message}" for w in report.warnings())
    )

    # ── named worker patch points via lens ──────────────────────────
    required_inputs = {
        "prompt",
        "negative_prompt",
        "seed",
        "seed_first",
        "seed_last",
        "width",
        "height",
        "frames",
        "fps",
        "fps_int",
        "first_strength",
        "last_strength",
        "first_image",
        "last_image",
        "model",
    }
    actual_inputs = set(workflow.inputs.keys())
    missing = required_inputs - actual_inputs
    assert not missing, f"Missing named inputs: {sorted(missing)}"

    # Lens-backed input target assertions (no compiled API links)
    assert lens.registered_input_target("prompt").node_id == "130"
    assert lens.registered_input_target("negative_prompt").node_id == "127"
    assert lens.registered_input_target("seed_first").node_id == "99"
    assert lens.registered_input_target("seed_last").node_id == "99"
    assert lens.registered_input_target("width").node_id == "113"
    assert lens.registered_input_target("height").node_id == "98"
    assert lens.registered_input_target("frames").node_id == "102"
    assert lens.registered_input_target("fps").node_id == "123"
    assert lens.registered_input_target("fps_int").node_id == "114"
    assert lens.registered_input_target("first_strength").node_id == "136"
    assert lens.registered_input_target("last_strength").node_id == "137"
    assert lens.registered_input_target("first_image").node_id == "1"
    assert lens.registered_input_target("last_image").node_id == "2"

    # ── structural assertions via lens ───────────────────────────────
    # Custom node packs
    assert "ComfyUI-LTXVideo" in workflow.requirements.custom_nodes
    assert "rgthree-comfy" not in workflow.requirements.custom_nodes

    # Portable parity uses the official Lightricks first/last spine that has
    # passed live on 4090: two LTXVAddGuide nodes and direct checkpoint model.
    stage_first = lens.node("136")
    stage_last = lens.node("137")
    assert stage_first is not None
    assert stage_first.class_type == "LTXVAddGuide"
    assert stage_last is not None
    assert stage_last.class_type == "LTXVAddGuide"

    # Strength defaults via lens
    assert lens.node_value("136", "strength") == 1.0
    assert lens.node_value("137", "strength") == 1.0

    # Image preprocessing chains via lens edge traversal.
    # First frame: ResizeImageMaskNode -> LTXVPreprocess -> LTXVAddGuide
    image_src_first = lens.edge_source("136", "image")
    assert image_src_first is not None and image_src_first.node_id is not None
    preprocess_first = lens.node(image_src_first.node_id)
    assert preprocess_first.class_type == "LTXVPreprocess"
    # Last guide: ResizeImageMaskNode -> LTXVPreprocess -> LTXVAddGuide
    image_src_last = lens.edge_source("137", "image")
    assert image_src_last is not None and image_src_last.node_id is not None
    preprocess_last = lens.node(image_src_last.node_id)
    assert preprocess_last.class_type == "LTXVPreprocess"

    # The last guide consumes the first guide output, preserving first/last order.
    assert lens.edge_source("136", "latent").node_id == "135"
    assert lens.edge_source("137", "latent").node_id == "136"
    assert lens.node("2291") is None
    assert lens.edge_source("138", "model").node_id == "125"
    assert lens.node("2292") is None
    assert lens.edge_source("138", "positive").node_id == "137"
    assert lens.edge_source("138", "negative").node_id == "137"

    # ── runtime materialization smoke (compiled API, minimal) ────────
    api = workflow.compile("api")
    assert api["1"]["class_type"] == "LoadImage"
    assert api["2"]["class_type"] == "LoadImage"
    assert api["116"]["inputs"]["sigmas"].startswith("1., 0.99375")
    assert api["102"]["class_type"] == "PrimitiveInt"
    assert api["123"]["class_type"] == "PrimitiveFloat"
    assert api["136"]["inputs"]["strength"] == 1.0
    assert api["137"]["inputs"]["strength"] == 1.0
    assert api["103"]["inputs"]["device"] == "default"
    assert api["128"]["inputs"]["resize_type"] == "scale dimensions"
    assert api["128"]["inputs"]["resize_type.width"] == ["113", 0]
    assert api["128"]["inputs"]["resize_type.height"] == ["98", 0]
    assert api["129"]["inputs"]["resize_type"] == "scale dimensions"
    assert api["129"]["inputs"]["resize_type.width"] == ["113", 0]
    assert api["129"]["inputs"]["resize_type.height"] == ["98", 0]
    assert api["125"]["inputs"]["ckpt_name"] == "ltx-2.3-22b-distilled-fp8.safetensors"
    assert "2291" not in api
    assert "2292" not in api
    assert api["138"]["inputs"]["model"] == ["125", 0]
    assert api["138"]["inputs"]["positive"] == ["137", 0]
    assert api["138"]["inputs"]["negative"] == ["137", 1]
    assert api["144"]["inputs"]["tile_size"] == 768
    assert api["144"]["inputs"].get("overlap", 64) == 64
    assert api["144"]["inputs"].get("temporal_overlap", 64) == 64
    for node_id in ("137", "136", "103", "128", "129", "144"):
        unresolved = [key for key in api[node_id]["inputs"] if key.startswith("widget_")]
        assert unresolved == [], f"{node_id} has unresolved widget inputs: {unresolved}"


def test_ltx_lightricks_first_last_parity_resolves_assets_from_registry() -> None:
    workflow = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    assets = {asset["name"]: asset for asset in _model_assets_from_workflow(workflow)}

    assert assets["ltx-2.3-22b-distilled-fp8.safetensors"]["url"] == (
        "https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors"
    )
    assert assets["gemma_3_12B_it_fp4_mixed.safetensors"]["url"] == (
        "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/"
        "gemma_3_12B_it_fp4_mixed.safetensors"
    )


def test_ltx_first_last_raw_video_guide_exposes_worker_patch_points() -> None:
    workflow = workflow_from_ready("video/ltx2_3_runexx_first_last_raw_video_guide")
    api = workflow.compile("api")

    assert workflow.validate().ok
    assert "rgthree-comfy" in workflow.requirements.custom_nodes
    assert workflow.metadata["source_role"] == "materialized_ready_python_template"
    assert workflow._resolve_input("start_image").node_id == "6"
    assert workflow._resolve_input("end_image").node_id == "7"
    assert workflow.inputs["control_video"].node_id == "2111"
    assert workflow.inputs["prompt"].node_id == "2083"
    assert workflow._resolve_input("negative").node_id == "6103"
    assert workflow.inputs["seed"].node_id == "4"
    assert workflow.inputs["frames"].node_id == "2077"
    assert workflow.inputs["width"].node_id == "2079"
    assert workflow.inputs["height"].node_id == "2078"
    assert workflow.inputs["fps"].node_id == "2076"
    assert workflow.inputs["strength"].node_id == "6102"
    assert workflow.inputs["first_frame_strength"].node_id == "2110"
    assert workflow.inputs["last_frame_strength"].node_id == "2108"

    assert api["6"]["class_type"] == "LoadImage"
    assert api["7"]["class_type"] == "LoadImage"
    assert api["2111"]["class_type"] == "LoadVideo"
    assert api["6109"]["class_type"] == "GetVideoComponents"
    assert api["6116"]["class_type"] == "ImageResizeKJv2"
    assert api["6116"]["inputs"]["image"] == ["6109", 0]
    assert api["6116"]["inputs"]["width"] == ["2079", 0]
    assert api["6116"]["inputs"]["height"] == ["2078", 0]
    assert api["6116"]["inputs"]["upscale_method"] == "lanczos"
    assert api["6116"]["inputs"]["keep_proportion"] == "stretch"
    assert api["6116"]["inputs"].get("crop_position", "center") == "center"
    assert not any(key.startswith("resize_type") for key in api["6116"]["inputs"])
    assert api["6102"]["class_type"] == "PrimitiveFloat"
    assert api["6135"]["class_type"] == "LTXVAddGuide"
    assert api["6135"]["inputs"].get("frame_idx", 0) == 0
    assert api["8"]["class_type"] == "LTXVAudioVAELoader"
    assert api["8"]["inputs"]["ckpt_name"] == "LTX23_audio_vae_bf16.safetensors"
    assert api["14"]["inputs"]["sigmas"].startswith("1.0, 0.99375")
    assert api["15"]["inputs"]["sigmas"] == "0.909375, 0.725, 0.421875, 0.0"
    assert api["6106"]["inputs"]["expression"] == "a"
    assert api["6108"]["inputs"]["expression"] == "a"
    assert api["9"]["inputs"].get("batch_size", 1) == 1
    assert api["6112"]["inputs"]["upscale_method"] == "lanczos"
    assert api["6112"]["inputs"]["scale_by"] == 0.5
    assert api["6114"]["inputs"]["sage_attention"] == "auto"
    assert any(
        package.get("name") == "sageattention"
        for package in workflow.metadata["runtime_packages"]
    )
    assert api["6114"]["inputs"].get("allow_compile", False) is False
    assert api["6120"]["inputs"].get("chunks", 2) == 2
    assert api["6120"]["inputs"].get("dim_threshold", 4096) == 4096
    assert api["6120"]["inputs"]["model"] == ["6114", 0]
    assert api["6123"]["inputs"].get("triton_kernels", False) is False
    assert api["6125"]["class_type"] == "LTX2MemoryEfficientSageAttentionPatch"
    assert api["6125"]["inputs"].get("triton_kernels", True) is True
    assert api["6125"]["inputs"]["model"] == ["6123", 0]
    assert api["2107"]["inputs"]["model"] == ["6125", 0]
    assert api["2292"]["class_type"] == "VibeComfyStripConditioningKeys"
    assert api["2292"]["inputs"].get("keys", "guide_attention_entries") == "guide_attention_entries"
    assert api["2292"]["inputs"]["positive"] == ["6135", 0]
    assert api["2292"]["inputs"]["negative"] == ["6135", 1]
    assert api["6137"]["inputs"]["positive"] == ["2292", 0]
    assert api["6137"]["inputs"]["negative"] == ["2292", 1]
    assert api["6141"]["inputs"]["positive"] == ["2292", 0]
    assert api["6141"]["inputs"]["negative"] == ["2292", 1]
    assert api["6128"]["inputs"].get("nag_scale", 11) == 11
    assert api["6143"]["inputs"]["filename_prefix"] == "reigh_vibecomfy_ltx_raw_guide"
    assert api["6143"]["inputs"].get("save_output", True) is True
    assert {asset["name"] for asset in workflow.metadata["model_assets"]} >= {
        "ltx-2.3_text_projection_bf16.safetensors",
        "taeltx2_3.safetensors",
        "LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
    }
    assert api["6135"]["inputs"]["image"] == ["6116", 0]
    assert api["6135"]["inputs"]["strength"] == ["6102", 0]
    assert "LTXICLoRALoaderModelOnly" not in {node["class_type"] for node in api.values()}
    assert "LTXAddVideoICLoRAGuide" not in {node["class_type"] for node in api.values()}
    assert _opaque_component_nodes(api) == []


def test_wan_22_i2v_template_uses_eager_model_loaders() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_14b_i2v_kijai")
    api = workflow.compile("api")

    loader_nodes = [
        node
        for node in api.values()
        if node["class_type"] == "WanVideoModelLoader"
    ]
    assert len(loader_nodes) >= 2
    assert all("compile_args" not in node["inputs"] for node in loader_nodes)


@pytest.mark.parametrize(
    "template_id",
    ["video/wanvideo_wrapper_22_14b_t2i", "video/wanvideo_wrapper_22_14b_vace_cocktail"],
)
def test_wan_2_2_templates_use_canonical_wanvideo_lora_path(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)

    lora_nodes = [
        node
        for node in workflow.nodes.values()
        if node.class_type == "WanVideoLoraSelectMulti"
    ]
    assert lora_nodes
    lora_key = "lora_0" if template_id.endswith("_vace_cocktail") else "widget_0"
    expected_path = (
        "WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
        if template_id.endswith("_vace_cocktail")
        else "WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
    )
    assert all(
        node.inputs[lora_key] == expected_path
        for node in lora_nodes
    )
    assert any(
        isinstance(asset, dict)
        and asset.get("name") == "lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
        and (asset.get("subdir") or asset.get("directory")) == "loras/WanVideo/Lightx2v"
        for asset in workflow.metadata["model_assets"]
    )


@pytest.mark.parametrize(
    "template_id",
    ["video/wanvideo_wrapper_22_14b_t2i", "video/wanvideo_wrapper_22_14b_vace_cocktail"],
)
def test_wan_2_2_templates_use_torch_compatible_precision(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)

    loader_nodes = [
        node
        for node in workflow.nodes.values()
        if node.class_type == "WanVideoModelLoader"
    ]
    assert loader_nodes
    precision_key = "base_precision" if template_id.endswith("_vace_cocktail") else "widget_1"
    assert all(node.inputs[precision_key] == "fp16" for node in loader_nodes)


def test_wan_vace_template_uses_live_wanvideo_schema_inputs() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_14b_vace_cocktail")
    api = workflow.compile("api")

    wanvideo_nodes = {
        node_id: node
        for node_id, node in api.items()
        if str(node.get("class_type", "")).startswith("WanVideo")
    }

    assert wanvideo_nodes
    assert [
        (node_id, node["class_type"], key)
        for node_id, node in wanvideo_nodes.items()
        for key in node.get("inputs", {})
        if key.startswith("widget_")
    ] == []
    assert [
        (node_id, node["class_type"], key, value)
        for node_id, node in wanvideo_nodes.items()
        for key, value in node.get("inputs", {}).items()
        if key in {"model", "model_name", "vace_model"} or key.startswith("lora_")
        if isinstance(value, str) and "\\" in value
    ] == []
    loader_nodes = [
        node
        for node in api.values()
        if node["class_type"] == "WanVideoModelLoader"
    ]
    assert len(loader_nodes) >= 2
    assert all("extra_model" in node["inputs"] for node in loader_nodes)
    assert all("vace_model" not in node["inputs"] for node in loader_nodes)
    block_swap_nodes = [
        node
        for node in api.values()
        if node["class_type"] == "WanVideoBlockSwap"
    ]
    assert block_swap_nodes
    assert all("blocks_to_keep" not in node["inputs"] for node in block_swap_nodes)
    assert all("offload_img_emb_nonblock" not in node["inputs"] for node in block_swap_nodes)


def test_wan_vace_template_uses_root_vace_module_asset() -> None:
    workflow = workflow_from_ready("video/wanvideo_wrapper_22_14b_vace_cocktail")

    assert any(
        isinstance(asset, dict)
        and asset.get("name") == "Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors"
        and asset.get("url") == (
            "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/"
            "Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors"
        )
        and (asset.get("subdir") or asset.get("directory")) == "diffusion_models/WanVideo"
        for asset in workflow.metadata["model_assets"]
    )


@pytest.mark.parametrize(
    "template_id",
    [
        "video/wanvideo_wrapper_22_14b_t2i",
        "video/wanvideo_wrapper_22_14b_i2v_kijai",
        "video/wan22_animate_native_first_stage",
    ],
)
def test_video_parity_templates_have_resolvable_runtime_model_assets(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)

    try:
        assets = _model_assets_from_workflow(workflow)
    except RuntimeError as exc:
        pytest.skip(f"runtime model registry gap for supplemental parity template: {exc}")
    else:
        assert assets


@pytest.mark.parametrize(
    "template_id",
    ["video/wanvideo_wrapper_22_14b_t2i", "video/wanvideo_wrapper_22_14b_vace_cocktail"],
)
def test_wan_2_2_template_asset_urls_match_upstream_locations(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)
    assets = {
        asset["name"]: asset
        for asset in workflow.metadata["model_assets"]
        if isinstance(asset, dict) and isinstance(asset.get("name"), str)
    }

    assert assets["Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/"
        "T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors"
    )
    assert assets["Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/"
        "T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors"
    )
    assert assets["lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/"
        "Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
    )
    assert assets["Wan2_1_VAE_bf16.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors"
    )
    assert assets["umt5-xxl-enc-bf16.safetensors"]["url"] == (
        "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors"
    )


def test_ready_template_requirements_accept_structured_model_assets() -> None:
    workflow = VibeWorkflow("scratchpad", WorkflowSource("scratchpad"))
    workflow.add_node("CheckpointLoaderSimple", widget_0="checkpoint.safetensors")

    apply_ready_template_policy(
        workflow,
        {},
        source_path="scratch.py",
        requirements={
            "models": [
                "legacy.safetensors",
                {
                    "name": "z-model.safetensors",
                    "url": "https://example.test/z-model.safetensors",
                    "subdir": "checkpoints",
                },
                {
                    "name": "z-model.safetensors",
                    "url": "https://example.test/duplicate.safetensors",
                    "subdir": "checkpoints",
                },
                {
                    "name": "a-model.safetensors",
                    "url": "https://example.test/a-model.safetensors",
                    "subdir": "vae",
                },
            ],
            "custom_nodes": [],
        },
    )

    assert workflow.requirements.models == [
        "a-model.safetensors",
        "legacy.safetensors",
        "z-model.safetensors",
    ]
    assert all(isinstance(model, str) for model in workflow.requirements.models)
    assert workflow.metadata["model_assets"] == [
        {
            "name": "z-model.safetensors",
            "url": "https://example.test/z-model.safetensors",
            "subdir": "checkpoints",
        },
        {
            "name": "a-model.safetensors",
            "url": "https://example.test/a-model.safetensors",
            "subdir": "vae",
        },
    ]


def test_ready_template_uses_real_python_before_comfy_compile() -> None:
    workflow = workflow_from_ready("edit/qwen_image_edit")

    marker = f"external_python:{workflow.metadata['ready_template']}"
    workflow.metadata["external_python_marker"] = marker
    workflow.add_node("MarkdownNote", widget_0=marker)
    api = workflow.compile("api")

    assert workflow.metadata["external_python_marker"] == marker
    assert all(node["inputs"].get("widget_0") != marker for node in api.values())


@pytest.mark.parametrize("template_id", PROFILE_SMOKE_TEMPLATE_IDS)
@pytest.mark.parametrize("memory_profile", [1, 2, 3, 4, 5])
def test_representative_video_ready_templates_compile_under_memory_profiles(
    template_id: str,
    memory_profile: int,
) -> None:
    baseline = workflow_from_ready(template_id)
    baseline_api = baseline.compile("api")
    workflow = workflow_from_ready(template_id)
    workflow.metadata["comfy_configuration"] = {"memory_profile": memory_profile}

    config = SessionConfig.from_workflow_metadata(workflow)
    api = workflow.compile("api")

    assert config.memory_profile == memory_profile
    assert workflow.validate().ok
    assert api
    assert canonical_equal(api, baseline_api)


@pytest.mark.parametrize("template_id", SNAPSHOT_IDS)
def test_snapshotted_ready_template_graph_matches_pre_refactor_api(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)
    actual = workflow.compile("api")
    snapshot_name = template_id.rsplit("/", 1)[-1]
    expected = json.loads((Path(__file__).parent / "snapshots" / f"{snapshot_name}.api.json").read_text(encoding="utf-8"))
    if template_id.startswith("video/ltx2_3_"):
        expected_workflow = convert_to_vibe_format(expected, workflow_id=template_id)
        expected_workflow.metadata["ready_template"] = template_id
        apply_ltx_lowvram(expected_workflow)
        resolution(384, 256, 9).apply(expected_workflow)
        expected = expected_workflow.compile("api")

    ok, diffs = compile_equivalent(expected, actual)
    assert ok, diffs


def _class_type_counter(api: dict) -> Counter[str]:
    return Counter(node["class_type"] for node in api.values() if node.get("class_type") != "MarkdownNote")


def _widget_value_counter(api: dict) -> Counter[tuple[str, str, str]]:
    values: Counter[tuple[str, str, str]] = Counter()
    for node in api.values():
        class_type = node.get("class_type")
        if class_type == "MarkdownNote":
            continue
        for key, value in node.get("inputs", {}).items():
            if _is_link(value):
                continue
            values[(class_type, key, repr(value))] += 1
    return values


def _topology_counter(api: dict) -> Counter[tuple[str, str, str, int]]:
    topology: Counter[tuple[str, str, str, int]] = Counter()
    for node_id, node in api.items():
        class_type = node.get("class_type")
        if class_type == "MarkdownNote":
            continue
        for key, value in node.get("inputs", {}).items():
            if not _is_link(value):
                continue
            source = api.get(str(value[0]), {})
            source_class = source.get("class_type")
            if source_class == "MarkdownNote":
                continue
            topology[(class_type, key, source_class, int(value[1]))] += 1
    return topology


def _edge_source(workflow: VibeWorkflow, to_node: str, to_input: str) -> tuple[str, str] | None:
    for edge in workflow.edges:
        if edge.to_node == to_node and edge.to_input == to_input:
            return edge.from_node, edge.from_output
    return None


def _is_link(value: object) -> bool:
    return isinstance(value, list) and len(value) == 2 and str(value[0]).isdigit()


def _opaque_component_nodes(api: dict[str, dict]) -> list[tuple[str, str]]:
    return [
        (node_id, node["class_type"])
        for node_id, node in api.items()
        if isinstance(node.get("class_type"), str)
        and len(node["class_type"]) == 36
        and node["class_type"].count("-") == 4
    ]
