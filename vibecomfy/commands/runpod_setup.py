from __future__ import annotations

import subprocess
import sys
import base64
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Sequence
import tomllib

from vibecomfy.registry import models_loader


BASELINE_MODEL_IDS = ("sd15_v1_5_pruned_emaonly_fp16",)
SMOKE_EXAMPLE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgaGAAAAIE"
    "AX6i7s8JAAAAAElFTkSuQmCC"
)
LTX_MODEL_PHASE = "ltx"
LTX_BASIC_MODEL_IDS = (
    "ltx_2_3_22b_dev_fp8",
    "ltx_2_3_text_encoder",
    "ltx_2_3_text_projection",
    "ltx_2_3_video_vae",
    "ltx_2_3_audio_vae",
    "ltx_2_3_preview_vae",
    "ltx_2_3_distilled_lora_384_1_1",
)
BASELINE_PYTHON_DEPS = ("glfw", "PyOpenGL")
NODE_PACK_COMPAT_DEPS = {
    # ComfyUI-LTXVideo@229437 imports kornia.geometry.transform.pyramid.pad,
    # which was removed in kornia 0.8.3.
    "ComfyUI-LTXVideo": ("kornia==0.8.2",),
}
RUNPOD_TORCH_DEPS = (
    "torch==2.8.0+cu128",
    "torchvision==0.23.0+cu128",
    "torchaudio==2.8.0+cu128",
)
RUNPOD_TORCH_INDEX_URL = "https://download.pytorch.org/whl/cu128"
BASELINE_PARKED_NODE_PACKS = ("ComfyUI-ResAdapter",)
RUNTIME_SUBDIRS = (
    "cache/pip",
    "cache/tmp",
    "cache/huggingface/hub",
    "cache/xdg",
    "input",
    "output",
    "custom_nodes",
    "disabled_custom_nodes",
    "models",
)
LTX_NODE_PACKS = (
    "ComfyUI-LTXVideo",
    "ComfyUI-KJNodes",
    "ComfyUI-VideoHelperSuite",
    "rgthree-comfy",
)


@dataclass(frozen=True)
class ParkedNodePack:
    name: str
    source: Path
    target: Path
    changed: bool


@dataclass(frozen=True)
class InstalledNodePack:
    name: str
    path: Path
    url: str
    commit: str
    changed: bool


@dataclass(frozen=True)
class LinkedCustomNode:
    source: Path
    target: Path
    changed: bool


def ensure_runtime_layout(*, runtime_root: Path, dry_run: bool = False) -> dict[str, Path]:
    paths = {name: runtime_root / name for name in RUNTIME_SUBDIRS}
    if not dry_run:
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
    else:
        for path in paths.values():
            print(f"mkdir -p {path}")
    return paths


def ensure_smoke_inputs(*, runtime_root: Path, dry_run: bool = False) -> list[Path]:
    """Create tiny default input files referenced by built-in smoke templates."""
    target = runtime_root / "input" / "example.png"
    if dry_run:
        print(f"write {target}")
        return [target]
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(base64.b64decode(SMOKE_EXAMPLE_PNG_B64))
    return [target]


def runtime_environment(*, runtime_root: Path) -> dict[str, str]:
    cache = runtime_root / "cache"
    return {
        "TMPDIR": str(cache / "tmp"),
        "PIP_CACHE_DIR": str(cache / "pip"),
        "HF_HOME": str(cache / "huggingface"),
        "HUGGINGFACE_HUB_CACHE": str(cache / "huggingface" / "hub"),
        "TRANSFORMERS_CACHE": str(cache / "huggingface" / "transformers"),
        "HF_HUB_DISABLE_XET": "1",
        "XDG_CACHE_HOME": str(cache / "xdg"),
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    }


def write_extra_model_paths(
    *,
    runtime_root: Path,
    path: Path | None = None,
    dry_run: bool = False,
) -> Path:
    target = path or runtime_root / "extra_model_paths.yaml"
    models = runtime_root / "models"
    content = f"""vibecomfy:
  base_path: {models}
  checkpoints: checkpoints
  clip: clip
  clip_vision: clip_vision
  configs: configs
  controlnet: controlnet
  diffusion_models: diffusion_models
  embeddings: embeddings
  loras: loras
  style_models: style_models
  unet: unet
  upscale_models: upscale_models
  vae: vae
  vae_approx: vae_approx
  text_encoders: text_encoders
  audio_encoders: audio_encoders
"""
    if dry_run:
        print(f"write {target}")
        print(content.rstrip())
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def comfy_serve_command(
    *,
    runtime_root: Path,
    external_address: str | None,
    port: int = 19123,
    comfyui_executable: str = "comfyui",
) -> list[str]:
    command = [
        comfyui_executable,
        "serve",
        "--listen",
        "0.0.0.0",
        "--port",
        str(port),
        "--base-directory",
        str(runtime_root),
        "--extra-model-paths-config",
        str(runtime_root / "extra_model_paths.yaml"),
        "--input-directory",
        str(runtime_root / "input"),
        "--output-directory",
        str(runtime_root / "output"),
        "--temp-directory",
        str(runtime_root / "cache" / "tmp"),
        "--user-directory",
        str(runtime_root / "user"),
        "--enable-manager",
        "--lowvram",
        "--reserve-vram",
        "2",
        "--log-stdout",
    ]
    if external_address:
        command.extend(["--external-address", external_address])
    return command


def stage_baseline_models(
    *,
    models_root: Path,
    registry: Path | None = None,
    dry_run: bool = False,
) -> None:
    configure_workspace_cache(models_root=models_root)
    entries = models_loader.load_registry(registry)
    selected = models_loader._filter_entries(entries, ids=BASELINE_MODEL_IDS, select_phase=None)
    if dry_run:
        models_loader._print_dry_run(selected, models_root=models_root)
        return
    models_loader.stage_many(selected, models_root=models_root, ids=BASELINE_MODEL_IDS)


def stage_ltx_models(
    *,
    models_root: Path,
    registry: Path | None = None,
    full: bool = False,
    dry_run: bool = False,
) -> None:
    configure_workspace_cache(models_root=models_root)
    entries = models_loader.load_registry(registry)
    selected = models_loader._filter_entries(entries, ids=None, select_phase=LTX_MODEL_PHASE)
    ids = None if full else LTX_BASIC_MODEL_IDS
    if dry_run:
        models_loader._print_dry_run(models_loader._select_by_ids(selected, ids), models_root=models_root)
        return
    models_loader.stage_many(selected, models_root=models_root, ids=ids)


def configure_workspace_cache(*, models_root: Path) -> Path:
    cache_root = models_root.resolve().parent / "cache"
    hf_home = cache_root / "huggingface"
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_home / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(hf_home / "transformers"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))
    hf_home.mkdir(parents=True, exist_ok=True)
    return cache_root


def park_node_packs(
    *,
    custom_nodes: Path,
    disabled_custom_nodes: Path,
    node_packs: Sequence[str] = BASELINE_PARKED_NODE_PACKS,
    dry_run: bool = False,
) -> list[ParkedNodePack]:
    disabled_custom_nodes.mkdir(parents=True, exist_ok=True)
    results: list[ParkedNodePack] = []
    for name in node_packs:
        source = custom_nodes / name
        target = disabled_custom_nodes / name
        if not source.exists():
            results.append(ParkedNodePack(name=name, source=source, target=target, changed=False))
            continue
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing disabled node pack: {target}")
        if not dry_run:
            source.rename(target)
        results.append(ParkedNodePack(name=name, source=source, target=target, changed=True))
    return results


def unpark_node_packs(
    *,
    custom_nodes: Path,
    disabled_custom_nodes: Path,
    node_packs: Sequence[str] = BASELINE_PARKED_NODE_PACKS,
    dry_run: bool = False,
) -> list[ParkedNodePack]:
    custom_nodes.mkdir(parents=True, exist_ok=True)
    results: list[ParkedNodePack] = []
    for name in node_packs:
        source = disabled_custom_nodes / name
        target = custom_nodes / name
        if not source.exists():
            results.append(ParkedNodePack(name=name, source=source, target=target, changed=False))
            continue
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing node pack: {target}")
        if not dry_run:
            source.rename(target)
        results.append(ParkedNodePack(name=name, source=source, target=target, changed=True))
    return results


def install_python_deps(
    packages: Iterable[str] = BASELINE_PYTHON_DEPS,
    *,
    python: str = sys.executable,
    dry_run: bool = False,
) -> None:
    packages = tuple(packages)
    if not packages:
        return
    cmd = [python, "-m", "pip", "install", *packages]
    if dry_run:
        print(" ".join(cmd))
        return
    subprocess.check_call(cmd)


def install_runpod_torch(
    packages: Iterable[str] = RUNPOD_TORCH_DEPS,
    *,
    index_url: str = RUNPOD_TORCH_INDEX_URL,
    python: str = sys.executable,
    dry_run: bool = False,
) -> None:
    packages = tuple(packages)
    cmd = [python, "-m", "pip", "install", "--index-url", index_url, *packages]
    if dry_run:
        print(" ".join(cmd))
        return
    subprocess.check_call(cmd)


def install_node_packs(
    *,
    custom_nodes: Path,
    lockfile: Path,
    node_packs: Sequence[str] = LTX_NODE_PACKS,
    python: str = sys.executable,
    install_requirements: bool = True,
    dry_run: bool = False,
) -> list[InstalledNodePack]:
    lock = _load_node_lock(lockfile)
    custom_nodes.mkdir(parents=True, exist_ok=True)
    installed: list[InstalledNodePack] = []
    for name in node_packs:
        raw = lock.get(name)
        if not raw:
            raise KeyError(f"{name} is not present in {lockfile}")
        url = _required_lock_str(raw, "url", name)
        commit = _required_lock_str(raw, "git_commit_sha", name)
        target = custom_nodes / name
        changed = False
        if not target.exists():
            _run(["git", "clone", url, str(target)], dry_run=dry_run)
            changed = True
        if target.exists() or dry_run:
            _run(["git", "-C", str(target), "fetch", "--depth", "1", "origin", commit], dry_run=dry_run, check=False)
            _run(["git", "-C", str(target), "checkout", "--force", commit], dry_run=dry_run)
        if install_requirements:
            requirements = target / "requirements.txt"
            if requirements.exists() or dry_run:
                _run([python, "-m", "pip", "install", "--no-deps", "-r", str(requirements)], dry_run=dry_run, check=False)
            compat_deps = NODE_PACK_COMPAT_DEPS.get(name, ())
            if compat_deps:
                _run([python, "-m", "pip", "install", *compat_deps], dry_run=dry_run, check=False)
        installed.append(InstalledNodePack(name=name, path=target, url=url, commit=commit, changed=changed))
    return installed


def link_vibecomfy_custom_node(
    *,
    custom_nodes: Path,
    package_root: Path | None = None,
    link_name: str = "vibecomfy_custom_nodes",
    dry_run: bool = False,
) -> LinkedCustomNode:
    root = package_root or Path(__file__).resolve().parents[1]
    source = root / "vibecomfy" / "comfy_nodes"
    if not source.exists():
        raise FileNotFoundError(f"VibeComfy custom node source not found: {source}")
    if dry_run:
        print(f"mkdir -p {custom_nodes}")
    else:
        custom_nodes.mkdir(parents=True, exist_ok=True)
    legacy_target = custom_nodes / "vibecomfy"
    if legacy_target != custom_nodes / link_name and legacy_target.is_symlink() and legacy_target.resolve() == source.resolve():
        if dry_run:
            print(f"rm {legacy_target}")
        else:
            legacy_target.unlink()
    target = custom_nodes / link_name
    if target.is_symlink() and target.resolve() == source.resolve():
        return LinkedCustomNode(source=source, target=target, changed=False)
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing custom node path: {target}")
    if not dry_run:
        target.symlink_to(source, target_is_directory=True)
    return LinkedCustomNode(source=source, target=target, changed=True)


def _load_node_lock(lockfile: Path) -> dict[str, dict[str, object]]:
    with lockfile.open("rb") as handle:
        data = tomllib.load(handle)
    nodepacks = data.get("nodepacks")
    if not isinstance(nodepacks, dict):
        raise ValueError(f"{lockfile}: missing [nodepacks] table")
    return {str(key): value for key, value in nodepacks.items() if isinstance(value, dict)}


def _required_lock_str(raw: dict[str, object], key: str, name: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name}: lockfile field {key!r} must be a non-empty string")
    return value


def _run(cmd: Sequence[str], *, dry_run: bool, check: bool = True) -> subprocess.CompletedProcess[str] | None:
    if dry_run:
        print(" ".join(cmd))
        return None
    return subprocess.run(cmd, check=check, text=True)
