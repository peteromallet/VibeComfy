from __future__ import annotations
import importlib.util, json, shutil, subprocess, sys
from dataclasses import dataclass; from pathlib import Path
from typing import Callable, Literal, Protocol, Sequence
from urllib.parse import urlparse
from vibecomfy.node_packs import CustomNodePack, KNOWN_NODE_PACKS, resolve_node_packs, unresolved_class_types
from vibecomfy.node_packs_lockfile import LockEntry, upsert_lockfile_entry
from vibecomfy.registry.pack_resolver import PackNotFoundError, PackRef, resolve_pack
from vibecomfy.workflow import VibeWorkflow
InstallStatus = Literal["installed", "refreshed", "skipped_dirty", "failed"]
DEFAULT_INSTALL_ROOT = Path("custom_nodes"); """Canonical install root for custom node packs."""
CORE_COMFY_CLASSES = frozenset(
    {
        # core Comfy built-ins (original)
        "CFGGuider",
        "CLIPLoader",
        "CLIPTextEncode",
        "DualCLIPLoader",
        "ImageScaleBy",
        "KSamplerSelect",
        "LoadImage",
        "LoraLoaderModelOnly",
        "ManualSigmas",
        "PrimitiveBoolean",
        "PrimitiveFloat",
        "PrimitiveStringMultiline",
        "RandomNoise",
        "SamplerCustomAdvanced",
        "SaveImage",
        "UNETLoader",
        "VAEDecodeTiled",
        "VAELoader",
        # core Comfy built-ins confirmed from comfy_core / comfy_extras object_info snapshots
        "AudioConcat",
        "AudioEncoderEncode",
        "AudioEncoderLoader",
        "BasicScheduler",
        "CheckpointLoaderSimple",
        "ComfyMathExpression",
        "ComfySwitchNode",
        "ConditioningZeroOut",
        "CreateVideo",
        "EmptyAceStep1.5LatentAudio",
        "EmptyAudio",
        "EmptyImage",
        "GetVideoComponents",
        "ImageBlend",
        "ImageBatchExtendWithOverlap",
        "ImageBatchMulti",
        "KSampler",
        "LoadAudio",
        "LoadVideo",
        "LoadVideosFromFolder",
        "LTXVAddGuideMulti",
        "LTXVAudioVAEEncode",
        "LTXVGemmaCLIPModelLoader",
        "LTXVImgToVideoConditionOnly",
        "LTXVImgToVideoInplace",
        "LTXVLatentUpsampler",
        "LTXVPreprocessMasks",
        "LTXVSetVideoLatentNoiseMasks",
        "MaskPreview",
        "MaskToImage",
        "ModelSamplingAuraFlow",
        "ModelSamplingSD3",
        "NormalizeAudioLoudness",
        "PreviewAudio",
        "PreviewImage",
        "PrimitiveInt",
        "PrimitiveNode",
        "PrimitiveString",
        "Reroute",
        "ResizeImageMaskNode",
        "SaveAudioMP3",
        "SaveVideo",
        "SetLatentNoiseMask",
        "SimpleMath+",
        "SolidMask",
        "StringConcatenate",
        "TextEncodeAceStepAudio1.5",
        "TextGenerateLTX2Prompt",
        "TrimAudioDuration",
        "VAEDecode",
        "VAEDecodeAudio",
        "VAEEncode",
        "VRAM_Debug",
    }
)
class Runner(Protocol):
    def __call__(self, args: Sequence[str], *, check: bool, capture_output: bool, text: bool, cwd: str | Path | None = None) -> subprocess.CompletedProcess[str]: ...
@dataclass(frozen=True)
class InstallResult: name: str; status: InstallStatus; git_commit_sha: str | None; error: str | None
def _resolve_cm_cli(install_root: Path, runner: Runner) -> list[str] | None:
    script = install_root / "ComfyUI-Manager" / "cm-cli.py"; sibling = Path(sys.executable).with_name("cm-cli"); found = shutil.which("cm-cli")
    module = [sys.executable, "-m", "comfyui_manager.cm_cli"] if importlib.util.find_spec("comfyui_manager") and importlib.util.find_spec("comfyui_manager.cm_cli") else None
    return next((argv for argv in ([sys.executable, str(script)] if script.exists() else None, [str(sibling)] if sibling.exists() else None, [found] if found else None, module) if argv), None)
def install_pack(*, name: str | None = None, repo: str | None = None, force: bool = False, install_root: Path = DEFAULT_INSTALL_ROOT, lockfile_path: Path = Path("custom_nodes.lock"), runner: Runner = subprocess.run, cm_cli_resolver: Callable[[Path, Runner], list[str] | None] = _resolve_cm_cli) -> InstallResult:
    if name is None and repo is None: raise ValueError("install_pack requires either name or repo")
    pack = _pack_by_name(name) if name is not None else None
    resolved_ref: PackRef | None = None
    if pack is None and repo is None and name is not None:
        try:
            resolved_ref = resolve_pack(name).ref
        except PackNotFoundError as exc:
            raise ValueError(f"unknown custom node pack {name!r}; pass repo to install an uncatalogued pack") from exc
        repo = resolved_ref.url
    if pack is None and repo is None: raise ValueError(f"unknown custom node pack {name!r}; pass repo to install an uncatalogued pack")
    pack_name = name or _pack_name_from_repo(repo or "")
    if not pack_name: raise ValueError(f"could not infer custom node pack name from repo {repo!r}")
    repo_url = repo or (pack.repo if pack is not None else None)
    if repo_url is None: raise ValueError(f"missing repo URL for custom node pack {pack_name!r}")
    install_dir = install_root / pack_name
    if install_dir.exists(): return _refresh_existing(pack_name, repo_url, install_dir, force, lockfile_path, runner, pack=pack, pack_ref=resolved_ref)
    cm_cli_argv = cm_cli_resolver(install_root, runner)
    if cm_cli_argv is None: return _install_pack_via_clone(pack_name, repo_url, pack, install_dir, lockfile_path, runner, pack_ref=resolved_ref)
    try: runner([*cm_cli_argv, "install", pack_name], check=True, capture_output=True, text=True, cwd=install_root.parent)
    except (OSError, subprocess.CalledProcessError):
        return _install_pack_via_clone(pack_name, repo_url, pack, install_dir, lockfile_path, runner, pack_ref=resolved_ref)
    if not (install_dir / ".git").exists(): return _install_pack_via_clone(pack_name, repo_url, pack, install_dir, lockfile_path, runner, pack_ref=resolved_ref)
    sha = _git_head(install_dir, runner)
    if sha is None: return InstallResult(pack_name, "failed", None, f"failed to read git HEAD for {install_dir}")
    entry = _lock_entry_for_pack(pack_name, sha, repo_url, pack=pack, pack_ref=resolved_ref)
    if entry is None: return InstallResult(pack_name, "failed", None, f"failed to derive class_set for registry-driven pack {pack_name}")
    upsert_lockfile_entry(entry, lockfile_path); return InstallResult(pack_name, "installed", sha, None)
def _install_pack_via_clone(name: str, repo_url: str, pack: CustomNodePack | None, install_dir: Path, lockfile_path: Path, runner: Runner, *, pack_ref: PackRef | None = None) -> InstallResult:
    try: runner(["git", "clone", repo_url, str(install_dir)], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc: return InstallResult(name, "failed", None, _error_text(exc) or f"failed to clone {repo_url}")
    try: runner([sys.executable, "-m", "pip", "install", *pack.pip_packages], check=True, capture_output=True, text=True) if pack and pack.pip_packages else None
    except (OSError, subprocess.CalledProcessError) as exc: return InstallResult(name, "failed", None, _error_text(exc) or "failed to install pip packages")
    sha = _git_head(install_dir, runner)
    if sha is None: return InstallResult(name, "failed", None, f"failed to read git HEAD for {install_dir}")
    entry = _lock_entry_for_pack(name, sha, repo_url, pack=pack, pack_ref=pack_ref)
    if entry is None: return InstallResult(name, "failed", None, f"failed to derive class_set for registry-driven pack {name}")
    upsert_lockfile_entry(entry, lockfile_path); return InstallResult(name, "installed", sha, None)
def restore_pack(entry: LockEntry, *, install_root: Path = DEFAULT_INSTALL_ROOT, runner: Runner = subprocess.run) -> InstallResult:
    install_dir = install_root / entry.name
    pack = _pack_by_name(entry.name)
    if install_dir.exists():
        if (dirty := _git_porcelain(install_dir, runner)) is None or dirty: return InstallResult(entry.name, "failed" if dirty is None else "skipped_dirty", None, f"failed to inspect git status for {install_dir}" if dirty is None else f"{install_dir} has uncommitted changes; restore refused")
        if _git_head(install_dir, runner) == entry.git_commit_sha: return InstallResult(entry.name, "refreshed", entry.git_commit_sha, None)
        try: runner(["git", "-C", str(install_dir), "fetch", "origin"], check=True, capture_output=True, text=True); runner(["git", "-C", str(install_dir), "checkout", entry.git_commit_sha], check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc: return InstallResult(entry.name, "failed", None, _error_text(exc) or f"failed to restore {entry.name}")
        if (pip_error := _install_pack_pip_packages(entry.name, pack, runner)) is not None: return InstallResult(entry.name, "failed", None, pip_error)
        return InstallResult(entry.name, "refreshed", entry.git_commit_sha, None)
    try: runner(["git", "clone", entry.url, str(install_dir)], check=True, capture_output=True, text=True); runner(["git", "-C", str(install_dir), "checkout", entry.git_commit_sha], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc: return InstallResult(entry.name, "failed", None, _error_text(exc) or f"failed to restore {entry.name}")
    if (pip_error := _install_pack_pip_packages(entry.name, pack, runner)) is not None: return InstallResult(entry.name, "failed", None, pip_error)
    return InstallResult(entry.name, "installed", entry.git_commit_sha, None)
def _refresh_existing(name: str, repo_url: str, install_dir: Path, force: bool, lockfile_path: Path, runner: Runner, *, pack: CustomNodePack | None = None, pack_ref: PackRef | None = None) -> InstallResult:
    dirty = _git_porcelain(install_dir, runner)
    if dirty is None: return InstallResult(name, "failed", None, f"failed to inspect git status for {install_dir}")
    if dirty and not force: return InstallResult(name, "skipped_dirty", None, f"{install_dir} has uncommitted changes; pass --force to refresh the lockfile pin")
    sha = _git_head(install_dir, runner)
    if sha is None: return InstallResult(name, "failed", None, f"failed to read git HEAD for {install_dir}")
    entry = _lock_entry_for_pack(name, sha, repo_url, pack=pack, pack_ref=pack_ref)
    if entry is None: return InstallResult(name, "failed", None, f"failed to derive class_set for registry-driven pack {name}")
    upsert_lockfile_entry(entry, lockfile_path); return InstallResult(name, "refreshed", sha, None)
def missing_packs_for_workflow(workflow: VibeWorkflow) -> tuple[list[CustomNodePack], list[str]]:
    missing_classes = missing_class_types_for_workflow(workflow)
    packs = resolve_node_packs(missing_classes)
    unresolved = unresolved_class_types(missing_classes)
    return _merge_declared_requirement_packs(workflow, packs), unresolved


def _merge_declared_requirement_packs(workflow: VibeWorkflow, packs: list[CustomNodePack]) -> list[CustomNodePack]:
    by_name = {pack.name: pack for pack in KNOWN_NODE_PACKS}
    merged = {pack.name: pack for pack in packs}
    for name in workflow.requirements.custom_nodes:
        pack = by_name.get(name)
        if pack is not None:
            merged.setdefault(pack.name, pack)
    return sorted(merged.values(), key=lambda pack: pack.name.lower())


def missing_class_types_for_workflow(workflow: VibeWorkflow) -> set[str]: return {node.class_type for node in workflow.nodes.values()} - _known_schema_classes() - CORE_COMFY_CLASSES
def _pack_by_name(name: str | None) -> CustomNodePack | None: return next((pack for pack in KNOWN_NODE_PACKS if pack.name == name), None)
def _lock_entry_for_pack(name: str, sha: str, repo_url: str, *, pack: CustomNodePack | None, pack_ref: PackRef | None = None) -> LockEntry | None:
    class_set = tuple(sorted(pack.classes)) if pack is not None and pack.classes else ()
    if pack_ref is not None and pack_ref.source == "comfy-registry" and not class_set:
        return None
    return LockEntry(
        name=name,
        git_commit_sha=sha,
        url=repo_url,
        slug=(pack_ref.slug if pack_ref is not None else name),
        source=(pack_ref.source if pack_ref is not None else "git"),
        version=(pack_ref.version if pack_ref is not None else None),
        commit=sha,
        class_set=class_set,
        pip_packages=pack.pip_packages if pack is not None else (),
        class_schema_sha256=pack.class_schema_sha256 if pack_ref is not None and pack is not None else None,
    )
def _install_pack_pip_packages(name: str, pack: CustomNodePack | None, runner: Runner) -> str | None:
    if pack is None or not pack.pip_packages: return None
    try: runner([sys.executable, "-m", "pip", "install", *pack.pip_packages], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc: return _error_text(exc) or f"failed to install pip packages for {name}"
    return None
def _pack_name_from_repo(repo: str) -> str: return (name[:-4] if (name := Path((urlparse(repo).path or repo).rstrip("/")).name).endswith(".git") else name)
def _git(pack_dir: Path, args: list[str], runner: Runner) -> str | None:
    try: return runner(["git", "-C", str(pack_dir), *args], check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError): return None
def _git_porcelain(pack_dir: Path, runner: Runner) -> str | None: return _git(pack_dir, ["status", "--porcelain"], runner)
def _git_head(pack_dir: Path, runner: Runner) -> str | None: return (_git(pack_dir, ["rev-parse", "HEAD"], runner) or "").strip() or None
def _known_schema_classes(path: Path = Path("node_index.json")) -> set[str]:
    path = _resolve_node_index_path(path)
    if not path.exists():
        from vibecomfy.schema import get_authoring_schema_provider

        return set(get_authoring_schema_provider(node_index_path=path).schemas())
    try: rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc: raise ValueError(f"node_index.json at {path} is not valid JSON: {exc}") from exc
    except OSError as exc: raise ValueError(f"failed to read node_index.json at {path}: {exc}") from exc
    if not isinstance(rows, list): raise ValueError(f"node_index.json at {path} must contain a list of node schemas")
    return {str(row.get("class_type")) for row in rows if isinstance(row, dict) and row.get("class_type")}
def _resolve_node_index_path(path: Path) -> Path:
    if path.is_absolute() or path.exists() or path != Path("node_index.json"):
        return path
    repo_index = Path(__file__).resolve().parents[1] / "node_index.json"
    return repo_index if repo_index.exists() else path
def _error_text(exc: BaseException) -> str | None: return next((text.strip() for value in (getattr(exc, "stderr", None), getattr(exc, "stdout", None)) if isinstance((text := value.decode(errors="replace") if isinstance(value, bytes) else value), str) and text.strip()), str(exc) or None)
