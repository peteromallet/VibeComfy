from __future__ import annotations
import importlib.util, json, os, re, shutil, socket, subprocess, sys, tempfile, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence
from urllib.parse import urlparse
from ._defs import CustomNodePack, get_known_node_packs, resolve_node_packs, unresolved_class_types
from ._lockfile import LockEntry, upsert_lockfile_entry
from vibecomfy.registry.pack_resolver import PackNotFoundError, PackRef

# resolve_pack is imported lazily inside install_pack() so that monkeypatching
# vibecomfy.node_packs.resolve_pack correctly affects install_pack behaviour.
from vibecomfy.security.gate import current_gate_context, require_confirmation, requesting_provenance
from vibecomfy.workflow import VibeWorkflow
InstallStatus = Literal["installed", "refreshed", "skipped_dirty", "failed"]
DEFAULT_INSTALL_ROOT = Path("custom_nodes")  # Canonical install root for custom node packs.
INSTALL_STATE_DIR = ".vibecomfy-install-state"
SENTINEL_LEASE_SECONDS = 1800  # 30 minutes


def default_install_root() -> Path:
    """Return the canonical install root for custom node packs.

    When the local-library ``custom_nodes`` slot is configured (via env var
    or TOML) the configured path is returned.  Otherwise falls back to the
    repo-relative ``custom_nodes`` directory.
    """
    from vibecomfy.local_library import Slot, resolved_path

    configured = resolved_path(Slot.custom_nodes)
    return configured if configured is not None else Path("custom_nodes")
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
@dataclass(frozen=True)
class PipPreflightResult:
    ok: bool
    packages: tuple[str, ...] = ()
    unsupported: bool = False
    error: str | None = None
@dataclass(frozen=True)
class InstallBatchResult:
    ok: bool
    results: tuple[InstallResult, ...]
    preflight: PipPreflightResult

    @property
    def preflight_unsupported(self) -> bool:
        return self.preflight.unsupported
@dataclass(frozen=True)
class _InstallSentinel:
    path: Path
    unreadable: bool = False
    live_owner_pid: int | None = None

    @property
    def incomplete(self) -> bool:
        return self.path.exists() or self.unreadable

    @property
    def reason(self) -> str:
        if self.live_owner_pid is not None:
            return (
                f"incomplete install sentinel for {self.path.stem} is owned by active"
                f" process pid={self.live_owner_pid}: {self.path}"
            )
        if self.unreadable:
            return f"incomplete install sentinel for {self.path.stem} is corrupt or unreadable: {self.path}"
        return f"incomplete install sentinel is present: {self.path}"

    def write(self, *, phase: str, name: str, repo_url: str, install_dir: Path, git_commit_sha: str | None = None, error: str | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "name": name,
            "repo_url": repo_url,
            "install_dir": str(install_dir),
            "phase": phase,
            "complete": False,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "timestamp": time.time(),
        }
        if git_commit_sha is not None:
            payload["git_commit_sha"] = git_commit_sha
        if error is not None:
            payload["error"] = error
        tmp = self.path.with_name(f".{self.path.name}.{id(payload)}.tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

def _resolve_cm_cli(install_root: Path, runner: Runner) -> list[str] | None:
    script = install_root / "ComfyUI-Manager" / "cm-cli.py"; sibling = Path(sys.executable).with_name("cm-cli"); found = shutil.which("cm-cli")
    module = [sys.executable, "-m", "comfyui_manager.cm_cli"] if importlib.util.find_spec("comfyui_manager") and importlib.util.find_spec("comfyui_manager.cm_cli") else None
    return next((argv for argv in ([sys.executable, str(script)] if script.exists() else None, [str(sibling)] if sibling.exists() else None, [found] if found else None, module) if argv), None)
def install_pack(
    *,
    name: str | None = None,
    repo: str | None = None,
    force: bool = False,
    install_root: Path | None = None,
    lockfile_path: Path = Path("custom_nodes.lock"),
    runner: Runner = subprocess.run,
    cm_cli_resolver: Callable[[Path, Runner], list[str] | None] = _resolve_cm_cli,
    pack_ref: PackRef | None = None,
    checkout_ref: str | None = None,
    expected_commit: str | None = None,
) -> InstallResult:
    if install_root is None:
        install_root = default_install_root()
    if name is None and repo is None: raise ValueError("install_pack requires either name or repo")
    pack = _pack_by_name(name) if name is not None else None
    resolved_ref: PackRef | None = None
    if pack is None and repo is None and name is not None:
        try:
            from vibecomfy.node_packs import resolve_pack  # see module-level comment

            resolved_ref = pack_ref or resolve_pack(name).ref
        except PackNotFoundError as exc:
            raise ValueError(f"unknown custom node pack {name!r}; pass repo to install an uncatalogued pack") from exc
        repo = resolved_ref.url
    elif pack_ref is not None:
        resolved_ref = pack_ref
    if pack is None and repo is None: raise ValueError(f"unknown custom node pack {name!r}; pass repo to install an uncatalogued pack")
    pack_name = name or _pack_name_from_repo(repo or "")
    if not pack_name: raise ValueError(f"could not infer custom node pack name from repo {repo!r}")
    if resolved_ref is not None and not resolved_ref.slug:
        resolved_ref = _pack_ref_with_slug(resolved_ref, pack_name)
    repo_url = repo or (pack.repo if pack is not None else None)
    if repo_url is None: raise ValueError(f"missing repo URL for custom node pack {pack_name!r}")
    install_dir = install_root / pack_name
    sentinel = _install_sentinel(install_root, pack_name)
    if _has_incomplete_install(sentinel): return InstallResult(pack_name, "failed", None, sentinel.reason)
    if install_dir.exists():
        return _refresh_existing(
            pack_name,
            repo_url,
            install_dir,
            force,
            lockfile_path,
            runner,
            pack=pack,
            pack_ref=resolved_ref,
            checkout_ref=checkout_ref,
            expected_commit=expected_commit,
            sentinel=sentinel,
        )
    cm_cli_argv = cm_cli_resolver(install_root, runner)
    # S4 capability fence: gate AFTER parameter validation (name/repo lookup,
    # cm-cli path detection, directory-exists check) and BEFORE any subprocess
    # call (cm-cli install / git clone / pip install). Refusal raises
    # CapabilityFenceError before any process is spawned.
    require_confirmation(
        operation="install_pack",
        class_type=None,
        provenance=requesting_provenance.get(),
        capabilities=frozenset({"code_exec", "network", "filesystem_write"}),
        details={"name": pack_name, "repo": repo_url},
        ctx=current_gate_context(),
    )
    sentinel.write(phase="start", name=pack_name, repo_url=repo_url, install_dir=install_dir)
    if cm_cli_argv is None:
        return _install_pack_via_clone(
            pack_name,
            repo_url,
            pack,
            install_dir,
            lockfile_path,
            runner,
            pack_ref=resolved_ref,
            checkout_ref=checkout_ref,
            expected_commit=expected_commit,
            sentinel=sentinel,
        )
    try:
        sentinel.write(phase="cm_cli", name=pack_name, repo_url=repo_url, install_dir=install_dir)
        runner([*cm_cli_argv, "install", pack_name], check=True, capture_output=True, text=True, cwd=install_root.parent)
    except (OSError, subprocess.CalledProcessError):
        return _install_pack_via_clone(
            pack_name,
            repo_url,
            pack,
            install_dir,
            lockfile_path,
            runner,
            pack_ref=resolved_ref,
            checkout_ref=checkout_ref,
            expected_commit=expected_commit,
            sentinel=sentinel,
        )
    if not (install_dir / ".git").exists():
        return _install_pack_via_clone(
            pack_name,
            repo_url,
            pack,
            install_dir,
            lockfile_path,
            runner,
            pack_ref=resolved_ref,
            checkout_ref=checkout_ref,
            expected_commit=expected_commit,
            sentinel=sentinel,
        )
    checkout_error = _checkout_ref_and_verify(
        pack_name,
        repo_url,
        install_dir,
        checkout_ref,
        expected_commit,
        runner,
        sentinel=sentinel,
        fetch=False,
    )
    if checkout_error is not None:
        return InstallResult(pack_name, "failed", None, checkout_error)
    return _finalize_install(
        pack_name, repo_url, install_dir, lockfile_path, runner,
        pack=pack, pack_ref=resolved_ref, expected_commit=expected_commit, sentinel=sentinel,
    )


def _install_pack_via_clone(
    name: str,
    repo_url: str,
    pack: CustomNodePack | None,
    install_dir: Path,
    lockfile_path: Path,
    runner: Runner,
    *,
    pack_ref: PackRef | None = None,
    checkout_ref: str | None = None,
    expected_commit: str | None = None,
    sentinel: _InstallSentinel | None = None,
) -> InstallResult:
    sentinel = sentinel or _install_sentinel(install_dir.parent, name)
    try:
        sentinel.write(phase="clone", name=name, repo_url=repo_url, install_dir=install_dir)
        runner(["git", "clone", repo_url, str(install_dir)], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc: return InstallResult(name, "failed", None, _error_text(exc) or f"failed to clone {repo_url}")
    checkout_error = _checkout_ref_and_verify(
        name,
        repo_url,
        install_dir,
        checkout_ref,
        expected_commit,
        runner,
        sentinel=sentinel,
        fetch=False,
    )
    if checkout_error is not None:
        return InstallResult(name, "failed", None, checkout_error)
    return _finalize_install(
        name, repo_url, install_dir, lockfile_path, runner,
        pack=pack, pack_ref=pack_ref, expected_commit=expected_commit, sentinel=sentinel,
    )


def restore_pack(entry: LockEntry, *, install_root: Path | None = None, runner: Runner = subprocess.run, lockfile_path: Path = Path("custom_nodes.lock")) -> InstallResult:
    if install_root is None:
        install_root = default_install_root()
    install_dir = install_root / entry.name
    pack = _pack_by_name(entry.name)
    sentinel = _install_sentinel(install_root, entry.name)
    if _has_incomplete_install(sentinel): return InstallResult(entry.name, "failed", None, sentinel.reason)
    if install_dir.exists():
        current_head = _git_head(install_dir, runner)
        if (dirty := _git_porcelain(install_dir, runner)) is None or dirty: return InstallResult(entry.name, "failed" if dirty is None else "skipped_dirty", current_head, f"failed to inspect git status for {install_dir}" if dirty is None else f"{install_dir} has uncommitted changes; restore refused")
        if _git_head(install_dir, runner) == entry.git_commit_sha: return InstallResult(entry.name, "refreshed", entry.git_commit_sha, None)
        try:
            sentinel.write(phase="restore_fetch", name=entry.name, repo_url=entry.url or "", install_dir=install_dir)
            runner(["git", "-C", str(install_dir), "fetch", "origin"], check=True, capture_output=True, text=True)
            sentinel.write(phase="restore_checkout", name=entry.name, repo_url=entry.url or "", install_dir=install_dir)
            runner(["git", "-C", str(install_dir), "checkout", entry.git_commit_sha], check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc: return InstallResult(entry.name, "failed", None, _error_text(exc) or f"failed to restore {entry.name}")
        result = _finalize_install(
            entry.name, entry.url or "", install_dir, lockfile_path, runner,
            pack=pack, expected_commit=entry.git_commit_sha, sentinel=sentinel,
        )
        if result.status != "installed":
            return result
        return InstallResult(result.name, "refreshed", result.git_commit_sha, result.error)
    sentinel.write(phase="restore_start", name=entry.name, repo_url=entry.url or "", install_dir=install_dir)
    try:
        sentinel.write(phase="clone", name=entry.name, repo_url=entry.url or "", install_dir=install_dir)
        runner(["git", "clone", entry.url, str(install_dir)], check=True, capture_output=True, text=True)
        sentinel.write(phase="restore_checkout", name=entry.name, repo_url=entry.url or "", install_dir=install_dir)
        runner(["git", "-C", str(install_dir), "checkout", entry.git_commit_sha], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc: return InstallResult(entry.name, "failed", None, _error_text(exc) or f"failed to restore {entry.name}")
    return _finalize_install(
        entry.name, entry.url or "", install_dir, lockfile_path, runner,
        pack=pack, expected_commit=entry.git_commit_sha, sentinel=sentinel,
    )
def _refresh_existing(
    name: str,
    repo_url: str,
    install_dir: Path,
    force: bool,
    lockfile_path: Path,
    runner: Runner,
    *,
    pack: CustomNodePack | None = None,
    pack_ref: PackRef | None = None,
    checkout_ref: str | None = None,
    expected_commit: str | None = None,
    sentinel: _InstallSentinel | None = None,
) -> InstallResult:
    sentinel = sentinel or _install_sentinel(install_dir.parent, name)
    if _has_incomplete_install(sentinel): return InstallResult(name, "failed", None, sentinel.reason)
    current_head = _git_head(install_dir, runner)
    current_origin = _git_origin(install_dir, runner)
    if current_origin is None:
        return InstallResult(name, "skipped_dirty", current_head, f"{install_dir} is not a readable git clone; refusing to overwrite existing contents")
    if _normalize_git_remote(current_origin) != _normalize_git_remote(repo_url):
        return InstallResult(
            name,
            "skipped_dirty",
            current_head,
            f"{install_dir} points at {current_origin}, expected {repo_url}; refusing to overwrite existing clone",
        )
    dirty = _git_porcelain(install_dir, runner)
    if dirty is None: return InstallResult(name, "failed", None, f"failed to inspect git status for {install_dir}")
    if dirty and not force: return InstallResult(name, "skipped_dirty", current_head, f"{install_dir} has uncommitted changes; pass --force to refresh the lockfile pin")
    checkout_error = _checkout_ref_and_verify(
        name,
        repo_url,
        install_dir,
        checkout_ref,
        expected_commit,
        runner,
        sentinel=sentinel,
        fetch=True,
    )
    if checkout_error is not None:
        return InstallResult(name, "failed", None, checkout_error)
    result = _finalize_install(
        name, repo_url, install_dir, lockfile_path, runner,
        pack=pack, pack_ref=pack_ref, expected_commit=expected_commit, sentinel=sentinel,
    )
    if result.status != "installed":
        return result
    return InstallResult(result.name, "refreshed", result.git_commit_sha, result.error)


def preflight_pip_requirements(packs: Sequence[CustomNodePack], *, runner: Runner = subprocess.run) -> PipPreflightResult:
    packages = tuple(sorted({package for pack in packs for package in pack.pip_packages}))
    if not packages:
        return PipPreflightResult(ok=True)
    try:
        help_result = runner([sys.executable, "-m", "pip", "install", "--help"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return PipPreflightResult(ok=False, packages=packages, unsupported=True, error=_error_text(exc) or "failed to check pip install capabilities")
    help_text = f"{help_result.stdout}\n{help_result.stderr}"
    if "--dry-run" not in help_text or "--report" not in help_text:
        return PipPreflightResult(ok=False, packages=packages, unsupported=True, error="pip install does not support required --dry-run --report preflight")
    with tempfile.TemporaryDirectory(prefix="vibecomfy-pip-preflight-") as tmp:
        report_path = Path(tmp) / "pip-report.json"
        try:
            runner(
                [sys.executable, "-m", "pip", "install", "--dry-run", "--report", str(report_path), *packages],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            return PipPreflightResult(ok=False, packages=packages, error=_error_text(exc) or "pip dry-run preflight failed")
    return PipPreflightResult(ok=True, packages=packages)
def install_required_packs(
    packs: Sequence[CustomNodePack],
    *,
    force: bool = False,
    restore_entries: Sequence[LockEntry] | None = None,
    install_refs_by_name: Mapping[str, PackRef | LockEntry | dict[str, Any] | str] | None = None,
    install_root: Path = DEFAULT_INSTALL_ROOT,
    lockfile_path: Path = Path("custom_nodes.lock"),
    runner: Runner = subprocess.run,
    cm_cli_resolver: Callable[[Path, Runner], list[str] | None] = _resolve_cm_cli,
) -> InstallBatchResult:
    ordered_packs = tuple(packs)
    preflight = preflight_pip_requirements(ordered_packs, runner=runner)
    if not preflight.ok:
        error = preflight.error or "pip preflight failed"
        return InstallBatchResult(
            ok=False,
            results=tuple(InstallResult(pack.name, "failed", None, error) for pack in ordered_packs),
            preflight=preflight,
        )
    restore_by_name = {entry.name: entry for entry in restore_entries or ()}
    install_refs = install_refs_by_name or {}
    results: list[InstallResult] = []
    for pack in ordered_packs:
        authored_ref = install_refs.get(pack.name)
        entry = restore_by_name.get(pack.name) or _restore_entry_from_install_ref(pack, authored_ref)
        install_ref = _pack_ref_from_install_ref(authored_ref)
        if install_ref is not None and not install_ref.slug:
            install_ref = _pack_ref_with_slug(install_ref, pack.name)
        result = (
            restore_pack(entry, install_root=install_root, runner=runner, lockfile_path=lockfile_path)
            if entry is not None
            else install_pack(
                name=pack.name,
                force=force,
                install_root=install_root,
                lockfile_path=lockfile_path,
                runner=runner,
                cm_cli_resolver=cm_cli_resolver,
                pack_ref=install_ref,
                checkout_ref=(
                    install_ref.commit
                    if install_ref is not None and install_ref.commit
                    else install_ref.version if install_ref is not None else None
                ),
                expected_commit=install_ref.commit if install_ref is not None and _looks_like_commit(install_ref.commit) else None,
            )
        )
        if authored_ref is not None and entry is not None and result.status in {"installed", "refreshed"}:
            upsert_lockfile_entry(entry, lockfile_path)
        elif install_ref is not None and result.status in {"installed", "refreshed"} and result.git_commit_sha is not None:
            repo_url = install_ref.url or pack.repo
            resolved_entry = _lock_entry_for_pack(pack.name, result.git_commit_sha, repo_url, pack=pack, pack_ref=install_ref)
            if resolved_entry is not None:
                upsert_lockfile_entry(resolved_entry, lockfile_path)
        results.append(result)
    return InstallBatchResult(
        ok=all(result.status in {"installed", "refreshed"} for result in results),
        results=tuple(results),
        preflight=preflight,
    )
def missing_packs_for_workflow(workflow: VibeWorkflow) -> tuple[list[CustomNodePack], list[str]]:
    missing_classes = missing_class_types_for_workflow(workflow)
    packs = resolve_node_packs(missing_classes)
    unresolved = unresolved_class_types(missing_classes)
    return _merge_declared_requirement_packs(workflow, packs), unresolved


def _merge_declared_requirement_packs(workflow: VibeWorkflow, packs: list[CustomNodePack]) -> list[CustomNodePack]:
    by_name = {pack.name: pack for pack in get_known_node_packs()}
    merged = {pack.name: pack for pack in packs}
    for name in workflow.requirements.custom_nodes:
        pack = by_name.get(name)
        if pack is not None:
            merged.setdefault(pack.name, pack)
    return sorted(merged.values(), key=lambda pack: pack.name.lower())


def missing_class_types_for_workflow(workflow: VibeWorkflow) -> set[str]: return {node.class_type for node in workflow.nodes.values()} - _known_schema_classes() - CORE_COMFY_CLASSES
def _pack_by_name(name: str | None) -> CustomNodePack | None: return next((pack for pack in get_known_node_packs() if pack.name == name), None)
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
def _restore_entry_from_install_ref(pack: CustomNodePack, install_ref: PackRef | LockEntry | dict[str, Any] | str | None) -> LockEntry | None:
    if install_ref is None:
        return None
    if isinstance(install_ref, LockEntry):
        return install_ref
    pack_ref = _pack_ref_from_install_ref(install_ref)
    if pack_ref is None or not _looks_like_commit(pack_ref.commit):
        return None
    repo_url = pack_ref.url or pack.repo
    if not pack_ref.slug:
        pack_ref = _pack_ref_with_slug(pack_ref, pack.name)
    return _lock_entry_for_pack(pack.name, pack_ref.commit or "", repo_url, pack=pack, pack_ref=pack_ref)
def _pack_ref_from_install_ref(install_ref: PackRef | LockEntry | dict[str, Any] | str | None) -> PackRef | None:
    if install_ref is None or isinstance(install_ref, LockEntry):
        return None
    if isinstance(install_ref, PackRef):
        return install_ref
    if isinstance(install_ref, str):
        return PackRef(slug="", source="git", version=install_ref, commit=install_ref if _looks_like_commit(install_ref) else None)
    return PackRef(
        slug=str(install_ref.get("slug") or install_ref.get("name") or ""),
        source=str(install_ref.get("source") or "git"),
        version=str(install_ref["version"]) if install_ref.get("version") is not None else None,
        commit=str(install_ref["commit"]) if install_ref.get("commit") is not None else None,
        url=str(install_ref["url"]) if install_ref.get("url") is not None else None,
        path=str(install_ref["path"]) if install_ref.get("path") is not None else None,
        name=str(install_ref["name"]) if install_ref.get("name") is not None else None,
        registry_id=str(install_ref["registry_id"]) if install_ref.get("registry_id") is not None else None,
    )
def _pack_ref_with_slug(pack_ref: PackRef, slug: str) -> PackRef:
    return PackRef(
        slug=slug,
        source=pack_ref.source,
        version=pack_ref.version,
        commit=pack_ref.commit,
        url=pack_ref.url,
        path=pack_ref.path,
        name=pack_ref.name,
        registry_id=pack_ref.registry_id,
    )
def _checkout_ref_and_verify(
    name: str,
    repo_url: str,
    install_dir: Path,
    checkout_ref: str | None,
    expected_commit: str | None,
    runner: Runner,
    *,
    sentinel: _InstallSentinel,
    fetch: bool,
) -> str | None:
    if checkout_ref is None:
        return None
    try:
        if fetch:
            sentinel.write(phase="fetch", name=name, repo_url=repo_url, install_dir=install_dir)
            runner(["git", "-C", str(install_dir), "fetch", "origin"], check=True, capture_output=True, text=True)
        sentinel.write(phase="checkout", name=name, repo_url=repo_url, install_dir=install_dir)
        runner(["git", "-C", str(install_dir), "checkout", checkout_ref], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return _error_text(exc) or f"failed to checkout {checkout_ref} for {name}"
    if expected_commit is None:
        return None
    head = _git_head(install_dir, runner)
    if head is None:
        return f"failed to read git HEAD for {install_dir}"
    if head != expected_commit:
        return f"expected git HEAD {expected_commit} for {install_dir}, got {head}"
    return None
def _looks_like_commit(value: str | None) -> bool:
    return bool(value is not None and re.fullmatch(r"[0-9a-fA-F]{7,40}", value))
def _install_pack_pip_packages(name: str, pack: CustomNodePack | None, runner: Runner) -> str | None:
    if pack is None or not pack.pip_packages: return None
    try: runner([sys.executable, "-m", "pip", "install", *pack.pip_packages], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc: return _error_text(exc) or f"failed to install pip packages for {name}"
    return None
def _finalize_install(
    name: str,
    repo_url: str,
    install_dir: Path,
    lockfile_path: Path,
    runner: Runner,
    *,
    pack: CustomNodePack | None = None,
    pack_ref: PackRef | None = None,
    expected_commit: str | None = None,
    sentinel: _InstallSentinel,
) -> InstallResult:
    """Shared install finalization: pip deps, git HEAD verify, lockfile upsert, sentinel clear.

    All five install/restore paths (clone, cm-cli success, refresh,
    restore-existing, restore-clone) route through this single helper so that
    durable invariants — pip dependency installation, commit verification,
    lockfile entry derivation and upsert, and sentinel clearance — are
    applied uniformly and only after all work succeeds.
    """
    # 1. Install pip dependencies (no-op when pack has none).
    sentinel.write(phase="pip", name=name, repo_url=repo_url, install_dir=install_dir)
    if (pip_error := _install_pack_pip_packages(name, pack, runner)) is not None:
        return InstallResult(name, "failed", None, pip_error)
    # 2. Verify git HEAD.
    sentinel.write(phase="verification", name=name, repo_url=repo_url, install_dir=install_dir)
    sha = _git_head(install_dir, runner)
    if sha is None:
        return InstallResult(name, "failed", None, f"failed to read git HEAD for {install_dir}")
    if expected_commit is not None and sha != expected_commit:
        return InstallResult(name, "failed", sha, f"expected git HEAD {expected_commit} for {install_dir}, got {sha}")
    # 3. Derive lockfile entry.
    entry = _lock_entry_for_pack(name, sha, repo_url, pack=pack, pack_ref=pack_ref)
    if entry is None:
        return InstallResult(name, "failed", None, f"failed to derive class_set for registry-driven pack {name}")
    # 4. Upsert lockfile and clear sentinel — only after all durable work succeeds.
    sentinel.write(phase="lockfile", name=name, repo_url=repo_url, install_dir=install_dir, git_commit_sha=sha)
    upsert_lockfile_entry(entry, lockfile_path)
    sentinel.clear()
    return InstallResult(name, "installed", sha, None)


def _install_sentinel(install_root: Path, name: str) -> _InstallSentinel:
    """Create an install sentinel, recovering dead/stale/corrupt sentinels.

    Recovery rules (conservative):
    * No sentinel file -> fresh sentinel.
    * Corrupt / unreadable sentinel -> quarantine and return fresh sentinel
      (no active owner detectable).
    * Valid sentinel with structured owner metadata (pid, hostname, timestamp):
      - Same host, pid alive -> refuse (live owner).
      - Same host, pid dead -> recover (clear sentinel).
      - Different host, lease stale -> recover.
      - Different host, lease fresh -> refuse (owner may be active on other host).
    * Valid sentinel without owner metadata (legacy / incomplete) -> quarantine
      and return fresh sentinel (no active owner detectable).
    """
    path = install_root / INSTALL_STATE_DIR / f"{_safe_pack_slug(name)}.json"
    if not path.exists():
        return _InstallSentinel(path)

    # Attempt to read sentinel payload.
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("complete") is not False:
            # Malformed or already-complete marker — quarantine as corrupt.
            _quarantine_sentinel(path)
            return _InstallSentinel(path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # Unreadable / corrupt — quarantine.
        _quarantine_sentinel(path)
        return _InstallSentinel(path)

    # Valid, incomplete sentinel.  Check owner metadata.
    owner_pid = data.get("pid")
    owner_hostname = data.get("hostname")
    owner_timestamp = data.get("timestamp")

    if owner_pid is not None and owner_hostname is not None and owner_timestamp is not None:
        current_hostname = socket.gethostname()
        if owner_hostname == current_hostname:
            # Same host — we can test the process directly.
            if _process_alive(owner_pid):
                return _InstallSentinel(path, live_owner_pid=owner_pid)
            else:
                # Process is dead — safe to recover.
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                return _InstallSentinel(path)
        else:
            # Different host — fall back to lease staleness.
            if time.time() - owner_timestamp > SENTINEL_LEASE_SECONDS:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                return _InstallSentinel(path)
            else:
                return _InstallSentinel(path, live_owner_pid=owner_pid)
    else:
        # No structured owner metadata — no active owner detectable.
        _quarantine_sentinel(path)
        return _InstallSentinel(path)


def _has_incomplete_install(sentinel: _InstallSentinel) -> bool:
    return sentinel.incomplete


def _process_alive(pid: int) -> bool:
    """Return True if a process with *pid* exists on this host."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we cannot signal it — treat as alive.
        return True
    except OSError:
        # On some platforms os.kill(pid, 0) may raise OSError for
        # permission or ESRCH-like reasons; err conservatively.
        return True
    return True


def _quarantine_sentinel(path: Path) -> None:
    """Rename *path* to a ``.corrupt-<timestamp>`` sibling so it cannot block
    the next install."""
    ts = int(time.time())
    dest = path.with_name(f".corrupt-{ts}-{path.name}")
    # If the destination already exists (unlikely), append a counter.
    counter = 0
    while dest.exists():
        counter += 1
        dest = path.with_name(f".corrupt-{ts}-{counter}-{path.name}")
    try:
        path.rename(dest)
    except (OSError, FileNotFoundError):
        # Best-effort — if we cannot rename, try to unlink.
        try:
            path.unlink()
        except FileNotFoundError:
            pass
def _safe_pack_slug(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return slug or "pack"
def _pack_name_from_repo(repo: str) -> str: return (name[:-4] if (name := Path((urlparse(repo).path or repo).rstrip("/")).name).endswith(".git") else name)
def _git(pack_dir: Path, args: list[str], runner: Runner) -> str | None:
    try: return runner(["git", "-C", str(pack_dir), *args], check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError): return None
def _git_porcelain(pack_dir: Path, runner: Runner) -> str | None: return _git(pack_dir, ["status", "--porcelain"], runner)
def _git_origin(pack_dir: Path, runner: Runner) -> str | None: return (_git(pack_dir, ["config", "--get", "remote.origin.url"], runner) or "").strip() or None
def _git_head(pack_dir: Path, runner: Runner) -> str | None: return (_git(pack_dir, ["rev-parse", "HEAD"], runner) or "").strip() or None
def _normalize_git_remote(value: str) -> str:
    cleaned = value.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if cleaned.startswith("git@github.com:"):
        cleaned = f"https://github.com/{cleaned.split(':', 1)[1]}"
    return cleaned.rstrip("/").lower()
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
    repo_index = Path(__file__).resolve().parent.parent.parent / "node_index.json"
    return repo_index if repo_index.exists() else path
def _error_text(exc: BaseException) -> str | None: return next((text.strip() for value in (getattr(exc, "stderr", None), getattr(exc, "stdout", None)) if isinstance((text := value.decode(errors="replace") if isinstance(value, bytes) else value), str) and text.strip()), str(exc) or None)
