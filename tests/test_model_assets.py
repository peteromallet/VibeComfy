from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.errors import ModelAssetError
from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.model_assets import entries_from_scratchpad_path, extract_from_raw_workflow, resolve_referenced_assets
from vibecomfy.registry.models_loader import ModelEntry, ModelSource, ModelTarget
import vibecomfy.runtime.attempt as runtime_attempt
from vibecomfy.runtime.session import _model_assets_from_workflow
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def test_extract_from_raw_workflow_normalises_model_metadata() -> None:
    raw = {
        "nodes": [
            {
                "id": 30,
                "type": "UNETLoader",
                "properties": {
                    "models": [
                        {
                            "name": "fallback.safetensors",
                            "url": "https://example.test/models/fallback.safetensors?download=true",
                        }
                    ]
                },
            },
            {
                "id": 10,
                "type": "UnknownLoader",
                "properties": {
                    "models": [
                        {
                            "name": "explicit.safetensors",
                            "url": "https://example.test/models/explicit.safetensors?download=true&x=1",
                            "directory": "custom_dir",
                        },
                        {
                            "name": "skip-missing-url.safetensors",
                        },
                    ]
                },
            },
            {
                "id": 20,
                "type": "NoDirectoryLoader",
                "properties": {
                    "models": [
                        {
                            "name": "split.safetensors",
                            "url": "https://huggingface.co/org/repo/resolve/main/split_files/vae/split.safetensors?download=true",
                        },
                        {
                            "name": "explicit.safetensors",
                            "url": "https://example.test/models/explicit.safetensors?download=true",
                            "directory": "custom_dir",
                        },
                    ]
                },
            },
        ]
    }

    assert extract_from_raw_workflow(raw) == [
        {
            "name": "explicit.safetensors",
            "url": "https://example.test/models/explicit.safetensors?x=1",
            "subdir": "custom_dir",
        },
        {
            "name": "split.safetensors",
            "url": "https://huggingface.co/org/repo/resolve/main/split_files/vae/split.safetensors",
            "subdir": "vae",
        },
        {
            "name": "fallback.safetensors",
            "url": "https://example.test/models/fallback.safetensors",
            "subdir": "diffusion_models",
        },
    ]


def test_extract_from_raw_workflow_recurses_nested_subgraphs() -> None:
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "nodes": [
                        {
                            "id": "2",
                            "type": "CLIPLoader",
                            "properties": {
                                "models": [
                                    {
                                        "name": "outer.safetensors",
                                        "url": "https://example.test/outer.safetensors",
                                    }
                                ]
                            },
                        }
                    ],
                    "definitions": {
                        "subgraphs": [
                            {
                                "nodes": [
                                    {
                                        "id": "1",
                                        "type": "VAELoader",
                                        "properties": {
                                            "models": [
                                                {
                                                    "name": "inner.safetensors",
                                                    "url": "https://example.test/inner.safetensors",
                                                }
                                            ]
                                        },
                                    }
                                ]
                            }
                        ]
                    },
                }
            ]
        }
    }

    assert extract_from_raw_workflow(raw) == [
        {"name": "outer.safetensors", "url": "https://example.test/outer.safetensors", "subdir": "text_encoders"},
        {"name": "inner.safetensors", "url": "https://example.test/inner.safetensors", "subdir": "vae"},
    ]


def test_extract_from_raw_workflow_returns_empty_for_api_shaped_workflow() -> None:
    assert extract_from_raw_workflow({"1": {"class_type": "VAELoader", "inputs": {}}}) == []


def test_entries_from_scratchpad_path_reads_materialized_requirements(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "READY_REQUIREMENTS = {'models': ["
        "{'name': 'model.safetensors', 'url': 'https://example.test/model.safetensors?download=true', 'subdir': 'checkpoints'},"
        "'legacy.safetensors',"
        "{'name': 'model.safetensors', 'url': 'https://example.test/duplicate.safetensors', 'subdir': 'checkpoints'}"
        "], 'custom_nodes': []}\n",
        encoding="utf-8",
    )

    assert entries_from_scratchpad_path(scratchpad) == [
        {"name": "model.safetensors", "url": "https://example.test/model.safetensors", "subdir": "checkpoints"}
    ]


def test_entries_from_scratchpad_path_preserves_reproducibility_pins(tmp_path: Path) -> None:
    scratchpad = tmp_path / "pinned.py"
    scratchpad.write_text(
        "READY_REQUIREMENTS = {'models': ["
        "{'name': 'model.safetensors', 'url': 'https://example.test/model.safetensors', 'subdir': 'checkpoints', "
        "'sha256': 'abc', 'hf_revision': 'rev1', 'size_bytes': 42}"
        "]}\n",
        encoding="utf-8",
    )

    assert entries_from_scratchpad_path(scratchpad) == [
        {
            "name": "model.safetensors",
            "url": "https://example.test/model.safetensors",
            "subdir": "checkpoints",
            "sha256": "abc",
            "hf_revision": "rev1",
            "size_bytes": 42,
        }
    ]


def test_entries_from_scratchpad_path_resolves_literal_module_constants(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "MODEL_ASSETS = ["
        "{'name': 'from_constant.safetensors', 'url': 'https://example.test/from_constant.safetensors', 'subdir': 'vae'}"
        "]\n"
        "READY_REQUIREMENTS = {'models': MODEL_ASSETS, 'custom_nodes': []}\n",
        encoding="utf-8",
    )

    assert entries_from_scratchpad_path(scratchpad) == [
        {
            "name": "from_constant.safetensors",
            "url": "https://example.test/from_constant.safetensors",
            "subdir": "vae",
        }
    ]


def test_entries_from_scratchpad_path_respects_explicit_subdir_for_non_split_asset(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "READY_REQUIREMENTS = {'models': ["
        "{'name': 'flux-2-klein-4b-fp8.safetensors', "
        "'url': 'https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors', "
        "'subdir': 'diffusion_models'}"
        "], 'custom_nodes': []}\n",
        encoding="utf-8",
    )

    assert entries_from_scratchpad_path(scratchpad) == [
        {
            "name": "flux-2-klein-4b-fp8.safetensors",
            "url": "https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors",
            "subdir": "diffusion_models",
        }
    ]


def test_resolve_referenced_assets_preserves_classified_unresolved_references() -> None:
    workflow = VibeWorkflow("models", WorkflowSource("models"))
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "registry.safetensors"})
    workflow.nodes["2"] = VibeNode(
        "2",
        "UNETLoader",
        inputs={"unet_name": "https://example.test/models/external.safetensors"},
    )
    workflow.nodes["3"] = VibeNode("3", "VAELoader", inputs={"vae_name": "/models/vae/local.safetensors"})
    workflow.nodes["4"] = VibeNode("4", "LoraLoader", inputs={"lora_name": "./loras/patch.safetensors"})
    workflow.nodes["5"] = VibeNode("5", "CheckpointLoaderSimple", inputs={"ckpt_name": "missing.safetensors"})
    registry = [
        ModelEntry(
            id="registry",
            source=ModelSource(kind="url", url="https://example.test/registry.safetensors"),
            min_size=1,
            targets=(ModelTarget(node_pack="comfy_core", path="diffusion_models/registry.safetensors"),),
        )
    ]

    resolved, unresolved = resolve_referenced_assets(workflow, registry=registry)

    assert resolved == [
        {
            "name": "registry.safetensors",
            "url": "https://example.test/registry.safetensors",
            "subdir": "diffusion_models",
            "node_id": "1",
            "class_type": "UNETLoader",
            "field": "unet_name",
            "value": "registry.safetensors",
            "reference_type": "registry-backed",
            "downloadable": True,
        }
    ]
    assert {
        (item["node_id"], item["reference_type"], item["downloadable"], item["subdir"])
        for item in unresolved
    } == {
        ("2", "external-url", False, "diffusion_models"),
        ("3", "absolute-path", False, "vae"),
        ("4", "relative-path", False, "loras"),
        ("5", "relative-path", False, "checkpoints"),
    }
    assert all({"node_id", "class_type", "field", "value", "subdir"} <= set(item) for item in unresolved)


def test_model_asset_install_policy_still_ignores_non_registry_url_and_path_values() -> None:
    workflow = VibeWorkflow("models", WorkflowSource("models"))
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "https://example.test/model.safetensors"})
    workflow.nodes["2"] = VibeNode("2", "VAELoader", inputs={"vae_name": "/models/vae/local.safetensors"})
    workflow.nodes["3"] = VibeNode("3", "LoraLoader", inputs={"lora_name": "./loras/patch.safetensors"})

    assert _model_assets_from_workflow(workflow) == []

    workflow.nodes["4"] = VibeNode("4", "CheckpointLoaderSimple", inputs={"ckpt_name": "missing.safetensors"})
    with pytest.raises(ModelAssetError, match="unresolved workflow model assets"):
        _model_assets_from_workflow(workflow)


def test_attempt_report_serializes_classified_model_references(monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = VibeWorkflow("models", WorkflowSource("models"))
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "registry.safetensors"})
    workflow.nodes["2"] = VibeNode(
        "2",
        "UNETLoader",
        inputs={"unet_name": "https://example.test/models/external.safetensors"},
    )
    workflow.nodes["3"] = VibeNode("3", "VAELoader", inputs={"vae_name": "/models/vae/local.safetensors"})
    workflow.nodes["4"] = VibeNode("4", "LoraLoader", inputs={"lora_name": "./loras/patch.safetensors"})
    registry = [
        ModelEntry(
            id="registry",
            source=ModelSource(kind="url", url="https://example.test/registry.safetensors"),
            min_size=1,
            targets=(ModelTarget(node_pack="comfy_core", path="diffusion_models/registry.safetensors"),),
        )
    ]
    monkeypatch.setattr("vibecomfy.registry.models_loader.load_registry", lambda: registry)
    monkeypatch.setattr(runtime_attempt, "_collect_drift_for_bundle", lambda _workflow: {})

    bundle = runtime_attempt.build_attempt_bundle(workflow, {}, backend="api")

    manifest_by_node = {entry["node_id"]: entry for entry in bundle["model_manifest"]}
    assert {
        node_id: (entry["reference_type"], entry["downloadable"], entry.get("unresolved"))
        for node_id, entry in manifest_by_node.items()
    } == {
        "1": ("registry-backed", True, None),
        "2": ("external-url", False, True),
        "3": ("absolute-path", False, True),
        "4": ("relative-path", False, True),
    }
    assert manifest_by_node["1"] == {
        "name": "registry.safetensors",
        "subdir": "diffusion_models",
        "url": "https://example.test/registry.safetensors",
        "expected_sha256": None,
        "actual_sha256": None,
        "node_id": "1",
        "class_type": "UNETLoader",
        "field": "unet_name",
        "value": "registry.safetensors",
        "reference_type": "registry-backed",
        "downloadable": True,
    }
    for node_id, expected_subdir in {"2": "diffusion_models", "3": "vae", "4": "loras"}.items():
        assert {
            "node_id",
            "class_type",
            "field",
            "value",
            "subdir",
            "reference_type",
            "downloadable",
            "unresolved",
        } <= set(manifest_by_node[node_id])
        assert manifest_by_node[node_id]["subdir"] == expected_subdir
        assert manifest_by_node[node_id]["expected_sha256"] is None
        assert manifest_by_node[node_id]["actual_sha256"] is None


def test_model_install_policy_only_requires_registry_or_authored_downloadables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = VibeWorkflow("models", WorkflowSource("models"))
    workflow.metadata["model_assets"] = [
        {
            "name": "authored.safetensors",
            "url": "https://example.test/authored.safetensors",
            "subdir": "vae",
        }
    ]
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "registry.safetensors"})
    workflow.nodes["2"] = VibeNode(
        "2",
        "UNETLoader",
        inputs={"unet_name": "https://example.test/models/external.safetensors"},
    )
    workflow.nodes["3"] = VibeNode("3", "VAELoader", inputs={"vae_name": "/models/vae/local.safetensors"})
    workflow.nodes["4"] = VibeNode("4", "LoraLoader", inputs={"lora_name": "./loras/patch.safetensors"})
    registry = [
        ModelEntry(
            id="registry",
            source=ModelSource(kind="url", url="https://example.test/registry.safetensors"),
            min_size=1,
            targets=(ModelTarget(node_pack="comfy_core", path="diffusion_models/registry.safetensors"),),
        )
    ]
    monkeypatch.setattr("vibecomfy.registry.models_loader.load_registry", lambda: registry)

    assert _model_assets_from_workflow(workflow) == [
        {
            "name": "authored.safetensors",
            "url": "https://example.test/authored.safetensors",
            "subdir": "vae",
        },
        {
            "name": "registry.safetensors",
            "url": "https://example.test/registry.safetensors",
            "subdir": "diffusion_models",
            "node_id": "1",
            "class_type": "UNETLoader",
            "field": "unet_name",
            "value": "registry.safetensors",
            "reference_type": "registry-backed",
            "downloadable": True,
        },
    ]

    workflow.nodes["5"] = VibeNode("5", "CheckpointLoaderSimple", inputs={"ckpt_name": "missing.safetensors"})
    with pytest.raises(ModelAssetError) as exc_info:
        _model_assets_from_workflow(workflow)
    message = str(exc_info.value)
    assert "CheckpointLoaderSimple 5.ckpt_name='missing.safetensors'" in message
    assert "external.safetensors" not in message
    assert "local.safetensors" not in message
    assert "patch.safetensors" not in message


def test_real_wan_t2v_extracts_three_assets() -> None:
    entries = extract_from_raw_workflow(load_workflow_json("ready_templates/sources/official/video/wan_t2v.json"))

    assert [(entry["name"], entry["subdir"]) for entry in entries] == [
        ("wan2.1_t2v_1.3B_fp16.safetensors", "diffusion_models"),
        ("umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders"),
        ("wan_2.1_vae.safetensors", "vae"),
    ]
    assert all("?download=true" not in entry["url"] for entry in entries)


def test_real_flux2_subgraph_extracts_pre_policy_assets() -> None:
    entries = extract_from_raw_workflow(load_workflow_json("ready_templates/sources/official/image/flux2_klein_9b_t2i.json"))

    assert [(entry["name"], entry["subdir"]) for entry in entries] == [
        ("flux-2-klein-base-9b-fp8.safetensors", "diffusion_models"),
        ("qwen_3_8b_fp8mixed.safetensors", "text_encoders"),
        ("full_encoder_small_decoder.safetensors", "vae"),
    ]
