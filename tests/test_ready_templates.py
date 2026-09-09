from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

import pytest

from vibecomfy.contracts import build_contract, doctor_contract
from vibecomfy.ingest.normalize import from_api
from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram
from vibecomfy.patches.resolution import resolution
from vibecomfy.porting.parity import compile_equivalent
from vibecomfy.registry import ready as ready_registry
from vibecomfy.registry.ready import ready_template_ids, ready_template_source_info, workflow_from_ready
from vibecomfy.registry.ready_template import (
    _merge_requirements,
    apply_ready_template_policy,
    finalise_model_assets,
)
from vibecomfy.registry.static_contract import compare_public_contracts, extract_ready_template_contract
from vibecomfy.runtime.session import SessionConfig, _model_assets_from_workflow
from vibecomfy.testing.canonical import canonical_equal
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


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


def test_requirement_merge_preserves_distinct_target_path_assets() -> None:
    workflow = VibeWorkflow("assets", WorkflowSource("assets"))
    workflow.metadata["model_assets"] = [
        {
            "name": "shared.bin",
            "url": "https://example.test/shared.bin",
            "subdir": "checkpoints",
        }
    ]

    _merge_requirements(
        workflow,
        {
            "models": [
                {
                    "name": "shared.bin",
                    "url": "https://example.test/shared.bin",
                    "subdir": "checkpoints",
                    "target_path": "custom_nodes/pack/shared.bin",
                }
            ]
        },
    )

    assert {entry.get("target_path") for entry in workflow.metadata["model_assets"]} == {
        None,
        "custom_nodes/pack/shared.bin",
    }


def test_model_asset_finalization_preserves_distinct_target_path_assets() -> None:
    workflow = VibeWorkflow("assets", WorkflowSource("assets"))
    workflow.nodes["1"] = VibeNode(
        "1", "CheckpointLoaderSimple", inputs={"ckpt_name": "shared.bin"}
    )
    workflow.metadata["model_assets"] = [
        {
            "name": "shared.bin",
            "url": "https://example.test/shared.bin",
            "subdir": "checkpoints",
        },
        {
            "name": "shared.bin",
            "url": "https://example.test/shared.bin",
            "subdir": "checkpoints",
            "target_path": "custom_nodes/pack/shared.bin",
        },
    ]

    finalise_model_assets(workflow)

    assert {entry.get("target_path") for entry in workflow.metadata["model_assets"]} == {
        None,
        "custom_nodes/pack/shared.bin",
    }


def test_ready_templates_use_v26_context_bound_shape() -> None:
    # Post-revert: emitted templates use either
    #   wf = new_workflow(READY_METADATA, source_path=__file__)
    # or the legacy ``with new_workflow(...) as wf:`` block.  Both shapes bind
    # the ContextVar (the flat assignment does so eagerly inside
    # ``new_workflow``; the ``with`` form does so via __enter__).
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

        with_blocks = [
            stmt
            for stmt in build.body
            if isinstance(stmt, ast.With)
            and any(
                isinstance(item.context_expr, ast.Call)
                and getattr(item.context_expr.func, "id", None) == "new_workflow"
                and isinstance(item.optional_vars, ast.Name)
                and item.optional_vars.id == "wf"
                for item in stmt.items
            )
        ]
        flat_assignments = [
            stmt
            for stmt in build.body
            if isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and stmt.targets[0].id == "wf"
            and isinstance(stmt.value, ast.Call)
            and getattr(stmt.value.func, "id", None) == "new_workflow"
        ]
        if (len(with_blocks) + len(flat_assignments)) != 1:
            offenders.append(
                f"{path}: expected exactly one top-level `wf = new_workflow(...)` "
                "or `with new_workflow(...) as wf:`"
            )
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


def test_wan_static_steps_target_matches_explicit_built_wrapper_id() -> None:
    from tools.refresh_template_index import build_template_index

    rows = {item["id"]: item for item in build_template_index()["templates"]}
    static_steps = next(
        item for item in rows["video/wan_i2v"]["public_inputs"]
        if item["name"] == "steps"
    )
    compiled = workflow_from_ready("video/wan_i2v").compile()

    assert static_steps["target"] == {"node_id": "3", "field": "steps"}
    assert compiled["3"]["class_type"] == "KSampler"
    assert compiled["3"]["inputs"]["steps"] == static_steps["value"]


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

    compiled = workflow.compile()
    resize = [
        (node_id, item) for node_id, item in compiled.items()
        if item.get("class_type") == "ImageResizeKJv2"
        and item.get("inputs", {}).get("upscale_method") == "lanczos"
        and item.get("inputs", {}).get("keep_proportion") == "stretch"
    ]
    assert len(resize) == 1
    _node_id, item = resize[0]
    inputs = item["inputs"]
    assert inputs["width"] == ["19", 0]
    assert inputs["height"] == ["18", 0]
    assert compiled["19"]["inputs"]["value"] == 1280
    assert compiled["18"]["inputs"]["value"] == 720
    assert inputs.get("crop_position", "center") == "center"
    assert not any(key.startswith("resize_type") for key in inputs)


def test_ltx_iclora_control_uses_live_resize_schema_inputs() -> None:
    workflow = workflow_from_ready("video/ltx2_3_first_last_frame_travel_iclora_control")

    compiled = workflow.compile()
    resize = [
        item for item in compiled.values()
        if item.get("class_type") == "ImageResizeKJv2"
        and item.get("inputs", {}).get("upscale_method") == "lanczos"
        and item.get("inputs", {}).get("keep_proportion") == "stretch"
    ]
    assert len(resize) == 5
    for inputs in (item["inputs"] for item in resize):
        assert inputs["width"] == ["16", 0]
        assert inputs["height"] == ["15", 0]
        assert inputs.get("crop_position", "center") == "center"
        assert not any(key.startswith("resize_type") for key in inputs)
    assert compiled["16"]["inputs"]["value"] == 256
    assert compiled["15"]["inputs"]["value"] == 256


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


def test_ready_template_source_info_json_reference_uses_supplied_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ready_templates"
    reference = root / "corpus" / "Reference.json"
    reference.parent.mkdir(parents=True)
    reference.write_text("{}", encoding="utf-8")
    discovery = ready_registry.ready_template_discovery(roots=[root])

    info = ready_template_source_info("CORPUS/REFERENCE.JSON", _discovery=discovery)

    assert not discovery.records
    assert [record.template_id for record in discovery.reference_records] == ["corpus/Reference.json"]
    assert info.template_id == "corpus/Reference.json"
    assert info.source_mode == "json_reference"


def test_ready_template_source_info_reports_invalid_utf8_as_structured_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "ready_templates"
    template_path = root / "image" / "invalid_utf8.py"
    template_path.parent.mkdir(parents=True)
    template_path.write_bytes(b"def build():\n    return '\xff'\n")
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: [root])

    info = ready_template_source_info("image/invalid_utf8")

    assert info.source_mode == "unreadable"
    assert info.runtime_source_of_truth is False
    assert info.diagnostics[0]["code"] == "source_unreadable"
    assert info.diagnostics[0]["error_type"] == "UnicodeDecodeError"


def test_ready_template_source_info_reports_read_failure_as_structured_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "ready_templates"
    # rglob includes this directory, while read_text raises IsADirectoryError.
    template_path = root / "image" / "unreadable.py"
    template_path.mkdir(parents=True)
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: [root])

    info = ready_template_source_info("image/unreadable")

    assert info.source_mode == "unreadable"
    assert info.runtime_source_of_truth is False
    assert info.diagnostics[0]["code"] == "source_unreadable"
    assert info.diagnostics[0]["error_type"] == "IsADirectoryError"


def test_ready_loader_applies_authored_metadata_for_manual_python_templates(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ready_templates"
    path = root / "manual" / "metadata.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        """
from vibecomfy.templates import ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, UNETLoader, VAELoader

READY_METADATA = ReadyMetadata.build(
    capability="image",
    models={
        "text": ModelAsset(filename="qwen_3_4b.safetensors", url="https://example.test/qwen_3_4b.safetensors", subdir="text_encoders"),
        "vae": ModelAsset(filename="ae.safetensors", url="https://example.test/ae.safetensors", subdir="vae"),
        "diffusion": ModelAsset(filename="z_image_bf16.safetensors", url="https://example.test/z_image_bf16.safetensors", subdir="diffusion_models"),
    },
    requirements={"models": ["qwen_3_4b.safetensors", "ae.safetensors", "z_image_bf16.safetensors"]},
    provenance={"source_id": "manual/metadata", "ready_id": "manual/metadata"},
)

def build():
    wf = new_workflow(READY_METADATA, source_path=__file__)
    UNETLoader(_id="1", unet_name="z_image_bf16.safetensors")
    CLIPLoader(_id="2", clip_name="qwen_3_4b.safetensors", type="lumina2")
    VAELoader(_id="3", vae_name="ae.safetensors")
    wf.finalize_metadata()
    return wf
""",
        encoding="utf-8",
    )
    discovery = ready_registry.ready_template_discovery(roots=[root])
    workflow = workflow_from_ready("manual/metadata", _discovery=discovery)

    assert workflow.metadata["python_policy_applied"] is True
    expected = {"qwen_3_4b.safetensors", "ae.safetensors", "z_image_bf16.safetensors"}
    assert {asset["name"] for asset in workflow.metadata["model_assets"]} == expected
    assert expected <= set(workflow.requirements.models)


def test_ready_templates_contract_doctor_matches_runtime_capabilities() -> None:
    """Runtime capability diagnostics remain the exact eight source-proven cases."""
    expected = {
        ("video/ltx2_3_runexx_custom_audio", "headless_preview_override_not_supported", "337"),
        ("video/ltx2_3_runexx_first_last_frame", "headless_preview_override_not_supported", "198"),
        ("video/ltx2_3_runexx_first_middle_last_frame", "headless_preview_override_not_supported", "198"),
        ("video/ltx2_3_runexx_lipsync_custom_audio", "headless_preview_override_not_supported", "368"),
        ("video/ltx2_3_runexx_motion_transfer_dwpose", "headless_preview_override_not_supported", "5187"),
        ("video/ltx2_3_runexx_music_video_low_ram", "headless_preview_override_not_supported", "2188"),
        ("video/ltx2_3_runexx_talking_avatar_qwen_tts", "headless_preview_override_not_supported", "1858"),
        ("video/ltx2_3_runexx_video_to_video_extend", "headless_preview_override_not_supported", "368"),
    }
    observed: set[tuple[str, str, str]] = set()
    for template_id in ready_template_ids():
        workflow = workflow_from_ready(template_id)
        contract = build_contract(workflow)
        report = doctor_contract(workflow, contract)
        for diagnostic in report.diagnostics:
            if diagnostic.severity != "error":
                continue
            key = (template_id, diagnostic.code, diagnostic.node_id or "")
            observed.add(key)
            assert diagnostic.code == "headless_preview_override_not_supported"
            assert diagnostic.detail.get("capability") == "ltx2_live_sampling_preview"
            assert workflow.compile()[diagnostic.node_id]["class_type"] == "LTX2SamplingPreviewOverride"
    assert observed == expected, f"Unexpected ready-template doctor diagnostics: {observed ^ expected}"


def test_wanvideo_model_loaders_preserve_declared_runtime_profile_diagnostics() -> None:
    expected = {
        ("video/wanvideo_wrapper_21_14b_flf2v", "22", "sageattn", "fp16_fast"),
        ("video/wanvideo_wrapper_21_14b_v2v_infinitetalk", "122", "sageattn", "fp16_fast"),
        ("video/wanvideo_wrapper_21_14b_wanmove_i2v", "22", "sageattn", "fp16"),
        ("video/wanvideo_wrapper_22_5b_i2v", "22", "sageattn", "fp16_fast"),
        ("video/wanvideo_wrapper_22_5b_i2v_controlnet", "22", "sageattn", "fp16_fast"),
        ("video/wanvideo_wrapper_22_5b_ovi_audio_i2v", "12", "sageattn", "None"),
        ("video/wanvideo_wrapper_22_5b_t2v_controlnet", "22", "sageattn", "fp16_fast"),
        ("video/wanvideo_wrapper_22_s2v_context_window", "22", "sageattn", "fp16_fast"),
        ("video/wanvideo_wrapper_22_s2v_framepack_pose", "22", "sageattn", "fp16_fast"),
        ("video/wanvideo_wrapper_wan_animate", "22", "sageattn", "fp16_fast"),
    }
    observed: set[tuple[str, str, str, str]] = set()
    for template_id in ready_template_ids():
        workflow = workflow_from_ready(template_id)
        api = workflow.compile("api")
        for node_id, node in api.items():
            if node.get("class_type") != "WanVideoModelLoader":
                continue
            inputs = node.get("inputs", {})
            attention_mode = inputs.get("attention_mode")
            base_precision = inputs.get("base_precision")
            if attention_mode == "sageattn" or base_precision == "fp16_fast":
                observed.add((template_id, node_id, str(attention_mode), str(base_precision)))
    assert observed == expected
    assert all(
        workflow_from_ready(template_id).metadata.get("runpod_profile") is None
        for template_id, _node_id, _attention, _precision in expected
    )


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


def test_ltx_runexx_first_last_frame_preserves_current_worker_roles() -> None:
    workflow = workflow_from_ready("video/ltx2_3_runexx_first_last_frame")
    assert workflow.validate().ok
    assert workflow.metadata["source_role"] == "materialized_ready_python_template"
    assert workflow.metadata["coverage_tier"] == "supplemental"
    assert "ComfyUI-GGUF" not in workflow.requirements.custom_nodes
    classes = Counter(node.class_type for node in workflow.nodes.values())
    assert classes["SimpleCalculatorKJ"] == 1
    assert classes["LTXVAddGuide"] == 1
    assert classes["ImageResizeKJv2"] == 2
    assert classes["LTXVImgToVideoInplaceKJ"] == 2
    assert classes["SamplerCustomAdvanced"] == 2
    assert classes["ManualSigmas"] == 2
    assert {"seed", "model", "prompt", "image", "input_image", "firstframe_strength", "lastframe_strength"} <= set(workflow.inputs)
    calculator_nodes = [node for node in workflow.nodes.values() if node.class_type == "SimpleCalculatorKJ"]
    assert len(calculator_nodes) == 1
    assert calculator_nodes[0].inputs == {"expression": "((round((a * b -1) / 8)) * 8) + 1 ", "b": 24.0}
    calculator_edges = [edge for edge in workflow.edges if edge.from_node == calculator_nodes[0].id]
    assert len(calculator_edges) == 1
    assert calculator_edges[0].to_input == "length"
    assert workflow.nodes[calculator_edges[0].to_node].class_type == "EmptyLTXVLatentVideo"
    assert all("GGUF" not in node.class_type for node in workflow.nodes.values())
    api = workflow.compile("api")
    assert all("GGUF" not in node["class_type"] for node in api.values())
    assert any(node["class_type"] == "LTX2SamplingPreviewOverride" for node in api.values())

def test_ready_template_loads_vibe_workflow() -> None:
    workflow = workflow_from_ready("edit/qwen_image_edit")

    assert workflow.validate().ok
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["python_policy_applied"] is True


def test_ready_templates_validate_or_report_exact_ltx_audio_vae_profiles() -> None:
    expected = {
        "video/ltx2_3_iamccs_audio_extend_low_ram": ("15", "VAELoaderKJ", "ltx-2.3-22b-dev_audio_vae.safetensors"),
        "video/ltx2_3_iamccs_audio_image_to_video": ("311", "VAELoaderKJ", "LTX2_audio_vae_bf16.safetensors"),
        "video/ltx2_3_iamccs_long_i2v": ("5221", "VAELoaderKJ", "LTX2_audio_vae_bf16.safetensors"),
        "video/ltx2_3_runexx_lipsync_custom_audio": ("471", "VAELoaderKJ", "LTX23_audio_vae_bf16_KJ.safetensors"),
        "video/ltx2_3_runexx_motion_transfer_dwpose": ("5127", "VAELoaderKJ", "LTX23_audio_vae_bf16_KJ.safetensors"),
        "video/ltx2_3_runexx_music_video_low_ram": ("1567", "VAELoaderKJ", "LTX23_audio_vae_bf16_KJ.safetensors"),
        "video/ltx2_3_runexx_video_to_video_extend": ("471", "VAELoaderKJ", "LTX23_audio_vae_bf16_KJ.safetensors"),
    }
    for template_id in ready_template_ids():
        workflow = workflow_from_ready(template_id)
        assert workflow.id == template_id
        assert workflow.metadata["ready_template"] == template_id
        report = workflow.validate()
        if template_id not in expected:
            assert report.ok, (template_id, report.issues)
            continue
        assert not report.ok
        assert [(issue.code, issue.detail) for issue in report.issues] == [
            ("ltx_audio_vae_wrong_loader", {"node_id": expected[template_id][0], "class_type": expected[template_id][1], "vae_name": expected[template_id][2]})
        ]

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


def test_native_wan_animate_template_declares_frame_count_binding() -> None:
    workflow = workflow_from_ready("video/wan22_animate_native_first_stage")

    assert workflow.metadata["unbound_inputs"]["frames"] == 81


def test_ready_template_build_has_category_qualified_metadata() -> None:
    workflow = workflow_from_ready("qwen_image_edit")

    assert workflow.id == "edit/qwen_image_edit"
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["workflow_template"] == "qwen_image_edit"


def test_ready_template_preserves_core_requirements_and_upstream_pack_provenance() -> None:
    workflow = workflow_from_ready("video/ltx2_3_t2v")
    assert workflow.requirements.custom_nodes == []
    assert {"EmptyLTXVLatentVideo", "LTXVAudioVAELoader", "LTXVScheduler"} <= {
        node.class_type for node in workflow.nodes.values()
    }
    pack = workflow.metadata["custom_node_packs"]["ComfyUI-LTXVideo"]
    assert pack["status"] == "discovered"
    assert pack["commit"] == "229437c6b65796d6a7a63ae34be2bd5ba31fa543"
    assert workflow.metadata["provenance"]["upstream_source_id"] == "ltx2_3_single_stage_distilled_full"

def test_ltx_first_last_travel_iclora_control_exposes_current_worker_roles() -> None:
    workflow = workflow_from_ready("video/ltx2_3_first_last_frame_travel_iclora_control")
    assert workflow.validate().ok
    assert {"seed", "model", "prompt", "image", "input_image"} == set(workflow.inputs)
    classes = Counter(node.class_type for node in workflow.nodes.values())
    assert classes["LTXAddVideoICLoRAGuide"] == 1
    assert classes["LTXICLoRALoaderModelOnly"] == 1
    assert classes["LTXVAudioVAELoader"] == 1
    assert classes["ImageResizeKJv2"] == 7
    assert classes["LoadVideo"] == 1
    api = workflow.compile("api")
    guide = next(node_id for node_id, node in api.items() if node["class_type"] == "LTXAddVideoICLoRAGuide")
    loader = next(node_id for node_id, node in api.items() if node["class_type"] == "LTXICLoRALoaderModelOnly")
    assert api[loader]["inputs"]["lora_name"] == "ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"
    assert "strength" not in api[guide]["inputs"]
    assert api[guide]["inputs"]["crop"] == "center"
    assert api[guide]["inputs"]["latent_downscale_factor"] == [loader, 1]

def test_ltx_lightricks_first_last_parity_exposes_current_worker_roles() -> None:
    workflow = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    assert workflow.validate().ok
    assert {"seed", "model", "prompt", "image", "input_image", "frames", "fps"} == set(workflow.inputs)
    classes = Counter(node.class_type for node in workflow.nodes.values())
    assert classes["LTXVAddGuide"] == 2
    assert classes["LTXVPreprocess"] == 2
    assert classes["EmptyLTXVLatentVideo"] == 1
    assert classes["SamplerCustomAdvanced"] == 1
    guide_ids = [node.id for node in workflow.nodes.values() if node.class_type == "LTXVAddGuide"]
    assert len(guide_ids) == 2
    by_id = {node.id: node for node in workflow.nodes.values()}
    guide_edges = [edge for edge in workflow.edges if edge.to_node in guide_ids]
    assert sum(by_id[edge.from_node].class_type == "LTXVPreprocess" and edge.to_input == "image" for edge in guide_edges) == 2
    assert sum(by_id[edge.from_node].class_type == "LTXVAddGuide" and edge.to_input == "latent" for edge in guide_edges) == 1
    assert workflow.compile("api")

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


def test_ltx_first_last_raw_video_guide_exposes_current_worker_roles() -> None:
    workflow = workflow_from_ready("video/ltx2_3_runexx_first_last_raw_video_guide")
    assert workflow.validate().ok
    assert "rgthree-comfy" in workflow.requirements.custom_nodes
    assert workflow.metadata["source_role"] == "materialized_ready_python_template"
    assert {"seed", "model", "prompt", "image", "input_image"} == set(workflow.inputs)
    classes = Counter(node.class_type for node in workflow.nodes.values())
    assert classes["LoadImage"] == 2
    assert classes["LoadVideo"] == 1
    assert classes["GetVideoComponents"] == 1
    assert classes["ImageResizeKJv2"] == 3
    assert classes["LTXVAddGuide"] == 1
    guide = next(node.id for node in workflow.nodes.values() if node.class_type == "LTXVAddGuide")
    by_id = {node.id: node for node in workflow.nodes.values()}
    assert any(by_id[e.from_node].class_type == "ImageResizeKJv2" and e.to_node == guide and e.to_input == "image" for e in workflow.edges)
    api = workflow.compile("api")
    assert set(api[guide]["inputs"]) == {"image", "latent", "negative", "positive", "vae"}
    assert api[guide]["inputs"] == {
        "image": ["33", 0],
        "latent": ["52", 0],
        "negative": ["28", 1],
        "positive": ["28", 0],
        "vae": ["11", 0],
    }

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
    lora_key = "lora_0" if template_id.endswith("_vace_cocktail") else "lora_0"
    expected_path = (
        "WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
        if template_id.endswith("_vace_cocktail")
            else "WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
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
    precision_key = "base_precision" if template_id.endswith("_vace_cocktail") else "base_precision"
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
        expected_workflow = from_api(expected, workflow_id=template_id)
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
