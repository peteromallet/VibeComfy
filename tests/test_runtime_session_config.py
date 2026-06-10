from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
import types

import httpx
import pytest

import vibecomfy.comfy_command as comfy_command_module
from vibecomfy.memory_profile import MemoryProfile
from vibecomfy.runtime.session import (
    EmbeddedSession,
    SessionConfig,
    ServerSession,
    VibeSession,
    _comfy_server_argv,
    _comfyui_command,
    _embedded_configuration_for_session,
    _run_metadata,
    apply_memory_profile_override,
    model_fingerprint,
)
import vibecomfy.runtime.client as client_module
from vibecomfy.workflow import VibeOutput, VibeWorkflow, WorkflowSource

from tests._runtime_session_helpers import (
    FakeConfiguration,
    _workflow,
    fake_comfy,  # noqa: F401 -- pytest fixture imported for use in tests
)


def test_comfy_client_http_errors_include_response_body() -> None:
    request = httpx.Request("POST", "http://comfy.test/prompt")
    response = httpx.Response(400, request=request, text='{"error": "bad prompt", "node_id": "2077"}')

    with pytest.raises(RuntimeError) as exc_info:
        client_module._raise_for_status_with_body(response)

    message = str(exc_info.value)
    assert "400 Bad Request" in message
    assert "bad prompt" in message
    assert "2077" in message


def test_comfy_client_long_http_errors_keep_tail() -> None:
    request = httpx.Request("POST", "http://comfy.test/prompt")
    body = "start-" + ("x" * 25000) + "-node_id_2077"
    response = httpx.Response(400, request=request, text=body)

    with pytest.raises(RuntimeError) as exc_info:
        client_module._raise_for_status_with_body(response)

    message = str(exc_info.value)
    assert "start-" in message
    assert "response body truncated" in message
    assert "node_id_2077" in message


def test_run_metadata_groups_single_artifact_by_semantic_output() -> None:
    workflow = VibeWorkflow("runtime-test", WorkflowSource("runtime-test"))
    workflow.outputs.append(VibeOutput(node_id="9", output_type="SaveImage", name="image", artifact_kind="image"))
    metadata = _run_metadata(
        run_id="run-1",
        workflow=workflow,
        api_dict={},
        queued={"outputs": {}},
        outputs=["/tmp/out/image.png"],
        runtime="embedded",
    )

    assert metadata["artifact_paths"] == ["/tmp/out/image.png"]
    assert metadata["outputs"] == ["/tmp/out/image.png"]
    assert metadata["artifact_manifest"] == {
        "schema_version": 1,
        "by_output": {"image": ["/tmp/out/image.png"]},
        "unmapped": [],
        "attribution": [
            {"path": "/tmp/out/image.png", "output": "image", "method": "single_named_output"},
        ],
    }


def test_run_metadata_uses_filename_prefix_and_keeps_uncertain_artifacts_unmapped() -> None:
    workflow = VibeWorkflow("runtime-test", WorkflowSource("runtime-test"))
    workflow.outputs.extend(
        [
            VibeOutput(
                node_id="9",
                output_type="SaveImage",
                name="preview",
                artifact_kind="image",
                filename_prefix="previews/preview",
            ),
            VibeOutput(
                node_id="10",
                output_type="VHS_VideoCombine",
                name="clip",
                artifact_kind="video",
                filename_prefix="clips/clip",
            ),
        ]
    )
    metadata = _run_metadata(
        run_id="run-1",
        workflow=workflow,
        api_dict={},
        queued={"outputs": {}},
        outputs=[
            "/tmp/out/previews/preview_00001.png",
            "/tmp/out/clips/clip_00001.mp4",
            "/tmp/out/mystery.bin",
        ],
        runtime="embedded",
    )

    assert metadata["artifact_manifest"] == {
        "schema_version": 1,
        "by_output": {
            "preview": ["/tmp/out/previews/preview_00001.png"],
            "clip": ["/tmp/out/clips/clip_00001.mp4"],
        },
        "unmapped": ["/tmp/out/mystery.bin"],
        "attribution": [
            {
                "path": "/tmp/out/previews/preview_00001.png",
                "output": "preview",
                "method": "filename_prefix",
            },
            {
                "path": "/tmp/out/clips/clip_00001.mp4",
                "output": "clip",
                "method": "filename_prefix",
            },
        ],
    }


def test_from_workflow_metadata_raw_hiddenswitch_carries_through(
    fake_comfy, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "reserve_vram": 12,
        "cache_none": True,
        "fp8_e4m3fn_text_enc": True,
    }

    config = SessionConfig.from_workflow_metadata(workflow)

    assert config.reserve_vram_gb == 12
    assert config.cache_policy == "none"
    assert config.extra == {"fp8_e4m3fn_text_enc": True}
    embedded_config = _embedded_configuration_for_session(config)
    assert embedded_config.reserve_vram == 12
    assert embedded_config.cache_none is True
    assert embedded_config.fp8_e4m3fn_text_enc is True


def test_embedded_configuration_loads_extra_model_paths_from_cwd(
    fake_comfy, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extra_model_paths = tmp_path / "extra_model_paths.yaml"
    extra_model_paths.write_text("reigh_shared:\n  base_path: /workspace/models\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)

    embedded_config = _embedded_configuration_for_session(SessionConfig())

    assert embedded_config is not None
    assert embedded_config.extra_model_paths_config == [str(extra_model_paths)]


def test_embedded_configuration_preserves_explicit_extra_model_paths(
    fake_comfy, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extra_model_paths = tmp_path / "extra_model_paths.yaml"
    explicit_extra_model_paths = tmp_path / "explicit_extra_model_paths.yaml"
    extra_model_paths.write_text("cwd paths\n", encoding="utf-8")
    explicit_extra_model_paths.write_text("explicit paths\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "VIBECOMFY_COMFY_CONFIGURATION",
        json.dumps({"extra_model_paths_config": [str(explicit_extra_model_paths)]}),
    )

    embedded_config = _embedded_configuration_for_session(SessionConfig())

    assert embedded_config is not None
    assert embedded_config.extra_model_paths_config == [str(explicit_extra_model_paths)]


def test_session_config_from_dict_raw_hiddenswitch_mirror() -> None:
    config = SessionConfig.from_dict(
        {"reserve_vram": 12, "cache_none": True, "fp8_e4m3fn_text_enc": True}
    )

    assert config.reserve_vram_gb == 12
    assert config.cache_policy == "none"
    assert config.extra == {"fp8_e4m3fn_text_enc": True}


def test_session_config_from_dict_typed_names() -> None:
    config = SessionConfig.from_dict(
        {
            "port": 8200,
            "vram_policy": "high",
            "reserve_vram_gb": 2.0,
            "cache_policy": "lru:3",
            "warm_policy": "always",
        }
    )

    assert config == SessionConfig(
        port=8200,
        vram_policy="high",
        reserve_vram_gb=2.0,
        cache_policy="lru:3",
        warm_policy="always",
        extra={},
    )


def test_session_config_from_dict_mixed_typed_and_raw_hiddenswitch() -> None:
    config = SessionConfig.from_dict(
        {"port": 8200, "reserve_vram": 12, "fp8_e4m3fn_text_enc": True}
    )

    assert config.port == 8200
    assert config.reserve_vram_gb == 12
    assert config.extra == {"fp8_e4m3fn_text_enc": True}


def test_session_config_typed_values_override_raw_hiddenswitch_conflicts() -> None:
    config = SessionConfig.from_dict({"reserve_vram_gb": 2.0, "reserve_vram": 12})

    assert config.reserve_vram_gb == 2.0


def test_session_config_empty_dict_uses_defaults() -> None:
    assert SessionConfig.from_dict({}) == SessionConfig(extra={})


def test_session_config_memory_profile_overlay_uses_normal_precedence() -> None:
    config = SessionConfig.from_dict(
        {
            "memory_profile": 5,
            "vram_policy": "normal",
            "reserve_vram_gb": 8.0,
            "cache_policy": "none",
        }
    )

    assert config.memory_profile is MemoryProfile.MINIMUM
    assert config.vram_policy == "normal"
    assert config.reserve_vram_gb == 8.0
    assert config.cache_policy == "none"
    assert config.disable_smart_memory is True


def test_session_config_memory_profile_overlay_respects_raw_hiddenswitch_precedence() -> None:
    config = SessionConfig.from_dict(
        {
            "memory_profile": 1,
            "lowvram": True,
            "reserve_vram": 3.0,
            "cache_none": True,
        }
    )

    assert config.memory_profile is MemoryProfile.LOW_RAM
    assert config.vram_policy == "low"
    assert config.reserve_vram_gb == 3.0
    assert config.cache_policy == "none"


@pytest.mark.parametrize("value", [0, 6, -1, "1", 1.0, True])
def test_session_config_memory_profile_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError, match="integer from 1 to 5"):
        SessionConfig.from_dict({"memory_profile": value})


def test_from_workflow_metadata_applies_memory_profile_before_explicit_fields() -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }

    config = SessionConfig.from_workflow_metadata(workflow)

    assert config.memory_profile is MemoryProfile.VERY_LOW_VRAM
    assert config.vram_policy == "low"
    assert config.cache_policy == "none"
    assert config.reserve_vram_gb == 7.0


def test_explicit_memory_profile_override_wins_after_workflow_metadata_resolution() -> None:
    workflow = _workflow()
    workflow.metadata["comfy_configuration"] = {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }
    config = SessionConfig.from_workflow_metadata(workflow)

    resolved = apply_memory_profile_override(config, 5)

    assert config.memory_profile is MemoryProfile.VERY_LOW_VRAM
    assert config.cache_policy == "none"
    assert config.reserve_vram_gb == 7.0
    assert resolved.memory_profile is MemoryProfile.MINIMUM
    assert resolved.vram_policy == "low"
    assert resolved.cache_policy == "lru:1"
    assert resolved.reserve_vram_gb == 4.0
    assert resolved.disable_smart_memory is True
    assert workflow.metadata["comfy_configuration"] == {
        "memory_profile": 4,
        "cache_policy": "none",
        "reserve_vram_gb": 7.0,
    }


def test_memory_profiles_round_trip_to_embedded_config_and_server_argv(fake_comfy) -> None:
    expected = {
        1: {"vram": "--highvram", "cache": None, "reserve": None, "disable": False},
        2: {"vram": "--highvram", "cache": ("--cache-lru", "32"), "reserve": None, "disable": False},
        3: {"vram": "--normalvram", "cache": None, "reserve": None, "disable": False},
        4: {"vram": "--lowvram", "cache": "--cache-classic", "reserve": "2.0", "disable": False},
        5: {"vram": "--lowvram", "cache": ("--cache-lru", "1"), "reserve": "4.0", "disable": True},
    }

    for value, profile_expected in expected.items():
        config = SessionConfig.from_dict({"memory_profile": value, "port": 8200})
        embedded = _embedded_configuration_for_session(config)
        argv = _comfy_server_argv(config)

        assert config.memory_profile == value
        assert embedded is not None
        assert getattr(embedded, profile_expected["vram"].removeprefix("--")) is True
        assert profile_expected["vram"] in argv
        assert argv[argv.index("--port") + 1] == "8200"

        cache = profile_expected["cache"]
        if cache is None:
            assert "--cache-lru" not in argv
            assert "--cache-classic" not in argv
            assert "--cache-none" not in argv
        elif isinstance(cache, tuple):
            flag, amount = cache
            assert argv[argv.index(flag) + 1] == amount
            assert getattr(embedded, flag.removeprefix("--").replace("-", "_")) == int(amount)
        else:
            assert cache in argv
            assert getattr(embedded, cache.removeprefix("--").replace("-", "_")) is True

        if profile_expected["reserve"] is None:
            assert "--reserve-vram" not in argv
            assert "reserve_vram" not in embedded
        else:
            assert argv[argv.index("--reserve-vram") + 1] == profile_expected["reserve"]
            assert embedded.reserve_vram == float(profile_expected["reserve"])

        if profile_expected["disable"]:
            assert "--disable-smart-memory" in argv
            assert embedded.disable_smart_memory is True
        else:
            assert "--disable-smart-memory" not in argv
            assert "disable_smart_memory" not in embedded


def test_sage_attention_profile_maps_to_embedded_config_and_server_argv(
    fake_comfy, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIBECOMFY_ATTENTION_PROFILE", "sage")

    embedded = _embedded_configuration_for_session(SessionConfig(port=8200))
    argv = _comfy_server_argv(SessionConfig(port=8200))

    assert embedded is not None
    assert embedded.use_sage_attention is True
    assert "--use-sage-attention" in argv


def test_server_argv_includes_configured_io_directories() -> None:
    config = SessionConfig.from_dict(
        {
            "port": 8200,
            "input_directory": "/tmp/vibe-input",
            "output_directory": "/tmp/vibe-output",
            "temp_directory": "/tmp/vibe-temp",
        }
    )

    argv = _comfy_server_argv(config)

    assert argv[argv.index("--input-directory") + 1] == "/tmp/vibe-input"
    assert argv[argv.index("--output-directory") + 1] == "/tmp/vibe-output"
    assert argv[argv.index("--temp-directory") + 1] == "/tmp/vibe-temp"
    assert argv[argv.index("--port") + 1] == "8200"


def test_comfyui_command_falls_back_to_runnable_python_module_when_script_shim_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    python = tmp_path / "python"
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(comfy_command_module.shutil, "which", lambda _name: str(tmp_path / "missing-comfyui"))
    monkeypatch.setattr(comfy_command_module.sys, "executable", str(python))
    monkeypatch.setattr(
        comfy_command_module.importlib.util,
        "find_spec",
        lambda name: object() if name == "comfy.cmd.main" else None,
    )

    assert _comfyui_command() == (str(python), "-m", "comfy.cmd.main")


def test_run_metadata_includes_memory_profile_telemetry_when_configured() -> None:
    metadata = _run_metadata(
        run_id="run-test",
        workflow=_workflow(),
        api_dict={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        queued={"prompt_id": "prompt-test"},
        outputs=[],
        runtime="embedded",
        config=SessionConfig.from_dict({"memory_profile": 3}),
        timings={"queue_prompt_sec": 1.25},
    )

    assert metadata["memory_profile"] == 3
    assert metadata["memory_profile_label"] == "Low VRAM"
    assert metadata["timings"]["queue_prompt_sec"] == 1.25


def test_run_metadata_omits_memory_profile_telemetry_when_unset() -> None:
    metadata = _run_metadata(
        run_id="run-test",
        workflow=_workflow(),
        api_dict={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        queued={"prompt_id": "prompt-test"},
        outputs=[],
        runtime="embedded",
        config=SessionConfig(),
    )

    assert "memory_profile" not in metadata
    assert "memory_profile_label" not in metadata


def test_run_metadata_adds_origin_fields_from_workflow_metadata_only_when_present() -> None:
    workflow = _workflow()
    workflow.metadata["entrypoint"] = "op"
    workflow.metadata["layer"] = "ops/image.py:t2i"

    metadata = _run_metadata(
        run_id="run-test",
        workflow=workflow,
        api_dict={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        queued={"prompt_id": "prompt-test"},
        outputs=[],
        runtime="embedded",
    )

    assert metadata["entrypoint"] == "op"
    assert metadata["layer"] == "ops/image.py:t2i"


def test_run_metadata_omits_new_fields_when_origin_and_chain_values_are_absent() -> None:
    metadata = _run_metadata(
        run_id="run-test",
        workflow=_workflow(),
        api_dict={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        queued={"prompt_id": "prompt-test"},
        outputs=[],
        runtime="embedded",
    )

    assert "entrypoint" not in metadata
    assert "layer" not in metadata
    assert "chain_id" not in metadata
    assert "parent_run_id" not in metadata


def test_run_metadata_includes_chain_fields_only_when_provided() -> None:
    metadata = _run_metadata(
        run_id="run-test",
        workflow=_workflow(),
        api_dict={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        queued={"prompt_id": "prompt-test"},
        outputs=[],
        runtime="embedded",
        chain_id="chain-1",
        parent_run_id="run-parent",
    )

    assert metadata["chain_id"] == "chain-1"
    assert metadata["parent_run_id"] == "run-parent"


def test_run_metadata_serializes_patch_applications_and_requirements() -> None:
    workflow = _workflow()
    workflow.metadata["patch_applications"] = [
        {
            "name": "seed:99",
            "called": True,
            "topology_changed": False,
            "nodes_added": [],
            "introduced_edges": [],
            "rewritten_edges": [],
            "value_changed": True,
        }
    ]
    workflow.requirements.models.extend(["model-a.safetensors"])
    workflow.requirements.custom_nodes.extend(["ComfyUI-ControlNet"])
    workflow.requirements.missing_models.extend(["missing-model.safetensors"])
    workflow.requirements.missing_nodes.extend(["MissingNode"])
    workflow.requirements.unsupported.extend(["legacy-widget"])

    metadata = _run_metadata(
        run_id="run-test",
        workflow=workflow,
        api_dict={"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        queued={"prompt_id": "prompt-test"},
        outputs=[],
        runtime="embedded",
    )

    assert metadata["patch_applications"] == workflow.metadata["patch_applications"]
    assert metadata["requirements"] == {
        "models": ["model-a.safetensors"],
        "custom_nodes": ["ComfyUI-ControlNet"],
        "missing_models": ["missing-model.safetensors"],
        "missing_nodes": ["MissingNode"],
        "unsupported": ["legacy-widget"],
    }
    assert json.dumps(metadata["requirements"], sort_keys=True)


def test_session_run_signatures_expose_chain_linkage_kwargs() -> None:
    for fn in (VibeSession.run, EmbeddedSession.run, ServerSession.run):
        params = inspect.signature(fn).parameters
        assert "chain_id" in params
        assert "parent_run_id" in params
        assert params["chain_id"].kind is inspect.Parameter.KEYWORD_ONLY
        assert params["parent_run_id"].kind is inspect.Parameter.KEYWORD_ONLY


def test_embedded_session_run_passes_chain_linkage_into_untracked_path(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_untracked(self, workflow, *, backend="api", strict_drift=False, chain_id=None, parent_run_id=None):
        captured.update(
            {
                "self": self,
                "workflow": workflow,
                "backend": backend,
                "strict_drift": strict_drift,
                "chain_id": chain_id,
                "parent_run_id": parent_run_id,
            }
        )
        return types.SimpleNamespace(run_id="embedded-run", prompt_id="prompt-1")

    monkeypatch.setattr(EmbeddedSession, "_run_untracked", fake_run_untracked)

    workflow = _workflow()
    session = EmbeddedSession()
    result = asyncio.run(
        session.run(
            workflow,
            backend="graphbuilder",
            strict_drift=True,
            chain_id="chain-1",
            parent_run_id="run-0",
        )
    )

    assert result.run_id == "embedded-run"
    assert result.prompt_id == "prompt-1"
    assert captured == {
        "self": session,
        "workflow": workflow,
        "backend": "graphbuilder",
        "strict_drift": True,
        "chain_id": "chain-1",
        "parent_run_id": "run-0",
    }


def test_server_session_run_passes_chain_linkage_into_untracked_path(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_untracked(self, workflow, *, backend="api", strict_drift=False, chain_id=None, parent_run_id=None):
        captured.update(
            {
                "self": self,
                "workflow": workflow,
                "backend": backend,
                "strict_drift": strict_drift,
                "chain_id": chain_id,
                "parent_run_id": parent_run_id,
            }
        )
        return types.SimpleNamespace(run_id="server-run", prompt_id="prompt-2")

    monkeypatch.setattr(ServerSession, "_run_untracked", fake_run_untracked)

    workflow = _workflow()
    session = ServerSession()
    result = asyncio.run(
        session.run(
            workflow,
            backend="graphbuilder",
            strict_drift=True,
            chain_id="chain-1",
            parent_run_id="run-0",
        )
    )

    assert result.run_id == "server-run"
    assert result.prompt_id == "prompt-2"
    assert captured == {
        "self": session,
        "workflow": workflow,
        "backend": "graphbuilder",
        "strict_drift": True,
        "chain_id": "chain-1",
        "parent_run_id": "run-0",
    }


def test_model_fingerprint_wan_snapshot() -> None:
    api = json.loads(Path("tests/snapshots/wan_t2v.api.json").read_text(encoding="utf-8"))

    # Post-v2.6 conversion strips schema-default loader fields from ready
    # templates and snapshots while preserving semantically selected models.
    assert model_fingerprint(api) == (
        ("CLIPLoader", "clip_name", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"),
        ("CLIPLoader", "type", "wan"),
        ("UNETLoader", "unet_name", "wan2.1_t2v_1.3B_fp16.safetensors"),
        ("VAELoader", "vae_name", "wan_2.1_vae.safetensors"),
    )


def test_model_fingerprint_ltx_snapshot_excludes_edge_references() -> None:
    api = json.loads(Path("tests/snapshots/ltx2_3_t2v.api.json").read_text(encoding="utf-8"))
    fingerprint = model_fingerprint(api)

    # Post-conversion: apply_ltx_lowvram swaps the ckpt to fp8; LoraLoaderModelOnly
    # widget_0 is now schema-resolved to lora_name; LTXAVTextEncoderLoader uses
    # canonical names from its source workflow JSON (text_encoder, not widget_0).
    assert ("LowVRAMCheckpointLoader", "ckpt_name", "ltx-2.3-22b-dev-fp8.safetensors") in fingerprint
    assert ("LowVRAMAudioVAELoader", "ckpt_name", "ltx-2.3-22b-dev-fp8.safetensors") in fingerprint
    assert (
        "LTXAVTextEncoderLoader",
        "text_encoder",
        "comfy_gemma_3_12B_it.safetensors",
    ) in fingerprint
    assert (
        "LoraLoaderModelOnly",
        "lora_name",
        "ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
    ) in fingerprint
    assert not any(slot in {"dependencies", "model"} for _, slot, _ in fingerprint)


def test_model_fingerprint_synthetic_gguf_loaders_excludes_edge_references() -> None:
    api = {
        "1": {
            "class_type": "DualCLIPLoaderGGUF",
            "inputs": {"clip_name1": "a.gguf", "clip_name2": "b.gguf", "clip": ["9", 0]},
        },
        "2": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": "wan.gguf", "model": ["1", 0]},
        },
    }

    assert model_fingerprint(api) == (
        ("DualCLIPLoaderGGUF", "clip_name1", "a.gguf"),
        ("DualCLIPLoaderGGUF", "clip_name2", "b.gguf"),
        ("UnetLoaderGGUF", "unet_name", "wan.gguf"),
    )
