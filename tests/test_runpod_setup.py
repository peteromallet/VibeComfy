from __future__ import annotations

from pathlib import Path

from vibecomfy.commands import runpod_setup
from vibecomfy.registry.models_loader import canonical_filename, load_registry


def test_baseline_registry_includes_sd15_fp16() -> None:
    entries = load_registry()

    assert canonical_filename("sd15_v1_5_pruned_emaonly_fp16", registry=entries) == "v1-5-pruned-emaonly-fp16.safetensors"


def test_configure_workspace_cache_defaults_to_models_parent(tmp_path: Path, monkeypatch) -> None:
    for name in ("HF_HOME", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)

    cache_root = runpod_setup.configure_workspace_cache(models_root=tmp_path / "vibecomfy" / "models")

    assert cache_root == (tmp_path / "vibecomfy" / "cache").resolve()
    assert Path(runpod_setup.os.environ["HF_HOME"]) == cache_root / "huggingface"
    assert Path(runpod_setup.os.environ["HUGGINGFACE_HUB_CACHE"]) == cache_root / "huggingface" / "hub"
    assert Path(runpod_setup.os.environ["XDG_CACHE_HOME"]) == cache_root / "xdg"


def test_runtime_layout_env_and_extra_model_paths(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    paths = runpod_setup.ensure_runtime_layout(runtime_root=runtime)
    extra = runpod_setup.write_extra_model_paths(runtime_root=runtime)
    env = runpod_setup.runtime_environment(runtime_root=runtime)

    assert paths["models"] == runtime / "models"
    assert (runtime / "custom_nodes").is_dir()
    assert env["HF_HOME"] == str(runtime / "cache" / "huggingface")
    assert env["HF_HUB_DISABLE_XET"] == "1"
    assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"
    assert "base_path: " + str(runtime / "models") in extra.read_text(encoding="utf-8")


def test_ensure_smoke_inputs_creates_example_png(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    paths = runpod_setup.ensure_smoke_inputs(runtime_root=runtime)

    assert paths == [runtime / "input" / "example.png"]
    assert paths[0].read_bytes().startswith(b"\x89PNG")


def test_comfy_serve_command_includes_runpod_public_flags(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    command = runpod_setup.comfy_serve_command(
        runtime_root=runtime,
        external_address="https://example.proxy.runpod.net",
        comfyui_executable="/venv/bin/comfyui",
    )

    assert command[:2] == ["/venv/bin/comfyui", "serve"]
    assert "--listen" in command
    assert "0.0.0.0" in command
    assert "--external-address" in command
    assert "https://example.proxy.runpod.net" in command
    assert "--extra-model-paths-config" in command
    assert str(runtime / "extra_model_paths.yaml") in command
    assert "--lowvram" in command
    assert "--reserve-vram" in command
    assert "--enable-cors-header" not in command
    assert "*" not in command
    assert "--highvram" not in command
    assert "--disable-dynamic-vram" not in command


def test_park_node_packs_moves_resadapter_out_of_custom_nodes(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    disabled = tmp_path / "disabled_custom_nodes"
    pack = custom_nodes / "ComfyUI-ResAdapter"
    pack.mkdir(parents=True)
    (pack / "__init__.py").write_text("", encoding="utf-8")

    result = runpod_setup.park_node_packs(custom_nodes=custom_nodes, disabled_custom_nodes=disabled)

    assert result[0].changed is True
    assert not pack.exists()
    assert (disabled / "ComfyUI-ResAdapter" / "__init__.py").exists()


def test_park_node_packs_dry_run_leaves_tree_in_place(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    disabled = tmp_path / "disabled_custom_nodes"
    pack = custom_nodes / "ComfyUI-ResAdapter"
    pack.mkdir(parents=True)

    result = runpod_setup.park_node_packs(custom_nodes=custom_nodes, disabled_custom_nodes=disabled, dry_run=True)

    assert result[0].changed is True
    assert pack.exists()


def test_unpark_node_packs_moves_resadapter_back_to_custom_nodes(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    disabled = tmp_path / "disabled_custom_nodes"
    pack = disabled / "ComfyUI-ResAdapter"
    pack.mkdir(parents=True)
    (pack / "__init__.py").write_text("", encoding="utf-8")

    result = runpod_setup.unpark_node_packs(custom_nodes=custom_nodes, disabled_custom_nodes=disabled)

    assert result[0].changed is True
    assert not pack.exists()
    assert (custom_nodes / "ComfyUI-ResAdapter" / "__init__.py").exists()


def test_link_vibecomfy_custom_node_links_package_source(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    package_root = tmp_path / "repo"
    source = package_root / "vibecomfy" / "comfy_nodes"
    source.mkdir(parents=True)

    result = runpod_setup.link_vibecomfy_custom_node(
        custom_nodes=custom_nodes,
        package_root=package_root,
    )

    assert result.changed is True
    assert result.target == custom_nodes / "vibecomfy_custom_nodes"
    assert result.target.resolve() == source.resolve()


def test_link_vibecomfy_custom_node_dry_run_does_not_create_parent(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "missing" / "custom_nodes"
    package_root = tmp_path / "repo"
    (package_root / "vibecomfy" / "comfy_nodes").mkdir(parents=True)

    result = runpod_setup.link_vibecomfy_custom_node(
        custom_nodes=custom_nodes,
        package_root=package_root,
        dry_run=True,
    )

    assert result.changed is True
    assert not custom_nodes.exists()


def test_link_vibecomfy_custom_node_removes_legacy_shadowing_symlink(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    package_root = tmp_path / "repo"
    source = package_root / "vibecomfy" / "comfy_nodes"
    source.mkdir(parents=True)
    custom_nodes.mkdir()
    (custom_nodes / "vibecomfy").symlink_to(source, target_is_directory=True)

    result = runpod_setup.link_vibecomfy_custom_node(
        custom_nodes=custom_nodes,
        package_root=package_root,
    )

    assert result.target == custom_nodes / "vibecomfy_custom_nodes"
    assert result.target.resolve() == source.resolve()
    assert not (custom_nodes / "vibecomfy").exists()


def test_install_node_packs_reads_lockfile_and_dry_runs(tmp_path: Path, capsys) -> None:
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text(
        """
[nodepacks.ComfyUI-LTXVideo]
url = "https://example.test/ltx.git"
git_commit_sha = "abc123"
""",
        encoding="utf-8",
    )

    result = runpod_setup.install_node_packs(
        custom_nodes=tmp_path / "custom_nodes",
        lockfile=lockfile,
        node_packs=("ComfyUI-LTXVideo",),
        dry_run=True,
    )

    assert result[0].name == "ComfyUI-LTXVideo"
    assert result[0].commit == "abc123"
    output = capsys.readouterr().out
    assert "git clone https://example.test/ltx.git" in output
    assert "pip install kornia==0.8.2" in output
    assert "git -C" in output


def test_install_runpod_torch_uses_cuda_128_index(capsys) -> None:
    runpod_setup.install_runpod_torch(python="/venv/bin/python", dry_run=True)

    output = capsys.readouterr().out
    assert "--index-url https://download.pytorch.org/whl/cu128" in output
    assert "torch==2.8.0+cu128" in output
    assert "torchvision==0.23.0+cu128" in output


def test_stage_ltx_models_default_is_basic_ttv_set(tmp_path: Path, capsys) -> None:
    runpod_setup.stage_ltx_models(models_root=tmp_path / "models", dry_run=True)

    output = capsys.readouterr().out
    assert "ltx-2.3-22b-dev-fp8.safetensors" in output
    assert "ltx-2.3-22b-distilled-lora-384-1.1.safetensors" in output
    assert "ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors" not in output
