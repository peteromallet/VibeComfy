"""VibeComfy-facing wrapper over the `runpod_lifecycle` package (v0.3.0).

All heavy lifting (launch, upload, exec, poll, download) lives in
``runpod_lifecycle.runner.ship_and_run{,_detached}``. This module adds only
vibecomfy-specific conventions: env-var lookups, the artifact-format reader
stack (delegated to ``runpod_artifacts``), and the ``run_pod`` /
``run_pod_detached`` entry points used by the acceptance/corpus/matrix scripts.

Env vars (read in ``_runpod_config_kwargs``)
--------------------------------------------
Credentials/defaults come from the *sibling* ``runpod-lifecycle`` repo's ``.env``
(see that package's skill). This wrapper reads vibecomfy-specific overrides:

- ``VIBECOMFY_RUNPOD_GPU``        CSV of GPU candidates (fanned across by the lifecycle).
                                  Default ``NVIDIA GeForce RTX 4090``.
- ``VIBECOMFY_RUNPOD_STORAGE``    primary network-volume name. Default ``Peter``.
- ``VIBECOMFY_RUNPOD_STORAGE_VOLUMES``  CSV of extra volumes tried after the primary
                                  (fan across datacenters — a single volume pins one DC).
- ``VIBECOMFY_RUNPOD_DISK_SIZE_GB`` / ``VIBECOMFY_RUNPOD_CONTAINER_DISK_GB``  pod/container disk.

v0.3.0 note: ``ship_and_run_detached`` no longer accepts ``guard_factory``,
``poll_command_template``, ``poll_exit_marker``, or ``artifact_paths``; this
wrapper relies on the lifecycle's hardcoded defaults (artifacts under
``["out", "output"]``, downloaded to ``local_root/"artifacts"``).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/workspace/vibecomfy"
MiB = 1024 * 1024
VIBECOMFY_RUNPOD_DISK_SIZE_ENV = "VIBECOMFY_RUNPOD_DISK_SIZE_GB"
VIBECOMFY_RUNPOD_CONTAINER_DISK_ENV = "VIBECOMFY_RUNPOD_CONTAINER_DISK_GB"

ARTIFACT_RUNS_ROOT = ROOT / "out" / "runpod_artifacts"

DEFAULT_UPLOAD_EXCLUDES: set[str] = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".desloppify", ".megaplan",
    "out", "output", "vendor", "ready_templates/sources", "custom_nodes", "input",
    "node_modules", ".mypy_cache", ".ruff_cache", ".DS_Store",
}


def _allocate_artifact_root() -> Path:
    """Allocate a unique final artifact root for this detached invocation."""
    publication_root = Path(ARTIFACT_RUNS_ROOT)
    if not _ensure_real_directory(publication_root):
        raise RuntimeError(
            f"RunPod artifact publication root is not a real directory without "
            f"symlink components: {publication_root}"
        )
    return publication_root / uuid.uuid4().hex


def _has_symlink_component(path: Path) -> bool:
    """Return whether an existing component of *path* is a symlink.

    This intentionally uses lexical parents and ``lstat``/``lexists`` rather
    than ``resolve``.  A missing leaf is acceptable while allocating a new
    destination, but a dangling link or a link in any existing parent is not.
    """
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    while True:
        try:
            if os.path.lexists(candidate):
                mode = os.lstat(candidate).st_mode
                if stat.S_ISLNK(mode):
                    return True
        except OSError:
            return True
        parent = candidate.parent
        if parent == candidate:
            return False
        candidate = parent


def _ensure_real_directory(path: Path) -> bool:
    """Create *path* if needed, requiring a real directory at every step.

    The frozen local-harness contract excludes concurrent same-user hostile
    replacement of the directory or its ancestors.  Residual pathname TOCTOU
    after the lexical recheck is accepted and non-blocking.
    """
    path = Path(path)
    if not path.is_absolute() or _has_symlink_component(path):
        return False
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    # Re-check after mkdir: a stale symlink or a concurrent replacement must
    # not become the publication root just because mkdir followed it.
    try:
        return path.is_dir() and not _has_symlink_component(path)
    except OSError:
        return False


def _destination_is_owned(
    destination: Path,
    publication_root: Path,
    *,
    allow_missing: bool,
) -> bool:
    """Validate a lexical destination below the real publication root."""
    destination = Path(destination)
    publication_root = Path(publication_root)
    if destination == publication_root:
        return False
    try:
        relative_destination = destination.relative_to(publication_root)
    except ValueError:
        return False
    if any(part == ".." for part in relative_destination.parts):
        return False
    if _has_symlink_component(publication_root) or _has_symlink_component(destination.parent):
        return False
    if not publication_root.is_dir() or publication_root.is_symlink():
        return False
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        return False
    destination_exists = os.path.lexists(destination)
    if allow_missing:
        return not destination_exists
    return destination_exists and destination.is_dir() and not destination.is_symlink()


def _stage_lifecycle_local_root(exclude: set[str]) -> Path:
    """Create an invocation-owned, mutation-isolated lifecycle root.

    ``runpod-lifecycle`` uses one ``local_root`` for both upload and artifact
    download. A private regular-file snapshot keeps that upload root isolated
    from the source checkout and from every other invocation.
    """
    staging_root = Path(tempfile.mkdtemp(prefix=".vibecomfy-runpod-", dir=ROOT.parent))
    staging_excludes = set(exclude) | {"artifacts"}

    def _ignore(directory: str, names: list[str]) -> list[str]:
        ignored: list[str] = []
        directory_path = Path(directory)
        for name in names:
            source = directory_path / name
            if should_skip(source, ROOT, staging_excludes):
                ignored.append(name)
        return ignored

    try:
        shutil.copytree(
            ROOT,
            staging_root,
            copy_function=shutil.copy2,
            ignore=_ignore,
            dirs_exist_ok=True,
        )
    except BaseException:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
    return staging_root


def _cleanup_lifecycle_local_root(staging_root: Path) -> None:
    """Remove only this invocation's private lifecycle staging root."""
    shutil.rmtree(staging_root, ignore_errors=True)


def _bind_artifact_root(
    artifact_root: Path | None,
    destination: Path,
    *,
    staging_root: Path,
) -> Path | None:
    """Move this invocation's download to its unique final artifact root.

    The lifecycle currently has a fixed download destination of
    ``local_root / "artifacts"``.  Treat that path as an ownership capability:
    only its exact lexical spelling is accepted.  In particular, resolving a
    path before comparing it would allow a symlink alias to pass the check and
    then move the alias itself out of the staging tree.

    The frozen local-harness contract excludes concurrent same-user hostile
    replacement of the publication root, destination parents, or staging
    ancestors.  Residual pathname TOCTOU after lexical rechecks is accepted
    and non-blocking.
    """
    if artifact_root is None:
        return None
    source = Path(artifact_root)
    expected = staging_root / "artifacts"
    if source != expected:
        return None
    if staging_root.is_symlink() or not staging_root.is_dir():
        return None
    if source.is_symlink() or not source.is_dir():
        return None
    if _has_symlink_component(staging_root) or _has_symlink_component(source):
        return None
    if _contains_symlink(source):
        return None
    publication_root = Path(ARTIFACT_RUNS_ROOT)
    if not _destination_is_owned(destination, publication_root, allow_missing=True):
        return None

    # Reserve the destination as an empty real directory.  This makes UUID
    # collisions and concurrent callers fail closed instead of replacing an
    # already-published run.  Recheck the complete lexical boundary directly
    # before the atomic directory rename as well.
    try:
        destination.mkdir()
    except OSError:
        return None
    if not _destination_is_owned(destination, publication_root, allow_missing=False):
        # Do not recursively remove a path after a boundary check failed: it
        # may have been replaced by another owner.  The invocation cleanup is
        # responsible for its private staging tree; this reserved path is
        # intentionally left as an auditable collision/failure marker.
        return None
    if destination.is_symlink() or _has_symlink_component(destination):
        return None
    try:
        source.replace(destination)
    except OSError:
        return None
    # The source is now published.  Check immediately after rename too, so a
    # parent replacement race cannot be reported as a successful safe bind.
    if destination.is_symlink() or _has_symlink_component(destination):
        return None
    if _contains_symlink(destination):
        return None
    return destination


def _contains_symlink(root: Path) -> bool:
    """Return whether *root* contains a symlink, including dangling links.

    ``Path.rglob`` and ordinary ``is_file``/``is_dir`` checks can follow or
    silently skip symlink aliases.  ``os.walk(..., followlinks=False)`` gives
    us the complete entry list while keeping traversal inside the downloaded
    tree; testing each entry with ``is_symlink`` catches both live and dangling
    links before the tree is moved to its durable artifact location.
    """
    try:
        for directory, child_dirs, child_files in os.walk(
            root, topdown=True, followlinks=False
        ):
            for name in (*child_dirs, *child_files):
                try:
                    if (Path(directory) / name).is_symlink():
                        return True
                except OSError:
                    # An inaccessible or concurrently removed entry cannot be
                    # proven safe, so fail closed at the artifact boundary.
                    return True
    except OSError:
        return True
    return False


def _runpod_config_kwargs() -> dict[str, Any]:
    config_kwargs: dict[str, Any] = {
        "storage_name": os.getenv("VIBECOMFY_RUNPOD_STORAGE", "Peter"),
        # Extra network volumes (CSV of names) to fan across datacenters when
        # the primary storage's DC has no GPU capacity. The lifecycle tries
        # every GPU against every resolved volume.
        "storage_volumes": tuple(
            v.strip()
            for v in os.getenv("VIBECOMFY_RUNPOD_STORAGE_VOLUMES", "").split(",")
            if v.strip()
        ),
        "gpu_type": _parse_gpu_type_env(
            os.getenv("VIBECOMFY_RUNPOD_GPU") or "NVIDIA GeForce RTX 4090"
        ),
        "ram_tiers": (32, 16),
    }
    if os.getenv(VIBECOMFY_RUNPOD_CONTAINER_DISK_ENV):
        config_kwargs["container_disk_gb"] = int(os.environ[VIBECOMFY_RUNPOD_CONTAINER_DISK_ENV])
    if os.getenv(VIBECOMFY_RUNPOD_DISK_SIZE_ENV):
        config_kwargs["disk_size_gb"] = int(os.environ[VIBECOMFY_RUNPOD_DISK_SIZE_ENV])
    return config_kwargs


def _bootstrap_lifecycle() -> None:
    """Make the sibling ``runpod-lifecycle`` package importable."""
    lifecycle_root = os.getenv("VIBECOMFY_RUNPOD_LIFECYCLE_ROOT")
    src = str(Path(lifecycle_root) / "src") if lifecycle_root else str(ROOT.parent / "runpod-lifecycle" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


_bootstrap_lifecycle()

from runpod_lifecycle import PodGuard  # noqa: E402
from runpod_lifecycle import UploadHeartbeat  # noqa: E402,F401
from runpod_lifecycle import install_signal_handlers  # noqa: E402
from runpod_lifecycle import should_skip  # noqa: E402,F401
from runpod_lifecycle import RunPodConfig  # noqa: E402
from runpod_lifecycle.config import _parse_gpu_type_env  # noqa: E402
from runpod_lifecycle import ship_and_run  # noqa: E402
from runpod_lifecycle import ship_and_run_detached  # noqa: E402
from runpod_lifecycle import ShipAndRunResult  # noqa: E402,F401
from runpod_lifecycle import _build_upload_tarball as _lifecycle_build_upload_tarball  # noqa: E402
from runpod_lifecycle import _preflight_upload_disk as _lifecycle_preflight_upload_disk  # noqa: E402

from runpod_lifecycle.runner import DEFAULT_POLL_COMMAND_TEMPLATE  # noqa: E402
from runpod_lifecycle.runner import DEFAULT_POLL_EXIT_MARKER  # noqa: E402
from scripts.runpod_artifacts import _parse_tsv  # noqa: E402,F401
from scripts.runpod_artifacts import _png_info  # noqa: E402,F401
from scripts.runpod_artifacts import _finalize_artifacts  # noqa: E402
from scripts.runpod_artifacts import _build_artifact_manifest  # noqa: E402,F401
from scripts.runpod_artifacts import _print_detached_summary  # noqa: E402

_ENV_BRIDGE_MAP: dict[str, str] = {
    "VIBECOMFY_UPLOAD_TMPDIR": "RUNPOD_LIFECYCLE_UPLOAD_TMPDIR",
    "VIBECOMFY_UPLOAD_MIN_FREE_BYTES": "RUNPOD_LIFECYCLE_UPLOAD_MIN_FREE_BYTES",
    "VIBECOMFY_UPLOAD_PROGRESS_SECONDS": "RUNPOD_LIFECYCLE_UPLOAD_PROGRESS_SECONDS",
    "VIBECOMFY_UPLOAD_PROGRESS_FILES": "RUNPOD_LIFECYCLE_UPLOAD_PROGRESS_FILES",
}


def _lifecycle_detached_remote_contract() -> str:
    """Describe the lifecycle's real detached launch, poll, and RC flow."""
    poll_command = DEFAULT_POLL_COMMAND_TEMPLATE.format(
        poll_exit_marker=DEFAULT_POLL_EXIT_MARKER
    )
    launch_command = (
        f"cd {REMOTE_ROOT} && rm -f {DEFAULT_POLL_EXIT_MARKER} && "
        "nohup bash /tmp/runpod-lifecycle-remote-run.sh "
        "> /tmp/runpod-lifecycle-remote-live.log 2>&1; "
        f'rc=$?; printf "%s" "$rc" > {DEFAULT_POLL_EXIT_MARKER}; exit "$rc"'
    )
    return (
        f"launch: {launch_command}; "
        f"poll: {poll_command}; "
        "propagation: lifecycle parses the marker as the detached return code "
        "and downloads artifacts after observing it"
    )


def _bridge_all_envs() -> None:
    """Forward vibecomfy env vars → lifecycle equivalents (call-time safe)."""
    for old_key, new_key in _ENV_BRIDGE_MAP.items():
        val = os.getenv(old_key)
        if val is not None and new_key not in os.environ:
            os.environ[new_key] = val


_bridge_all_envs()  # import-time; wrappers re-bridge at call time for monkeypatch


def _build_upload_tarball(exclude: set[str], *, root: Path = ROOT) -> Path:
    """Build a tarball of *root* (minus *exclude*) — vibecomfy-bridged."""
    _bridge_all_envs()
    return _lifecycle_build_upload_tarball(exclude, root=root)


def _preflight_upload_disk(temp_dir: Path, estimated_bytes: int) -> None:
    """Check local disk before upload — vibecomfy-bridged."""
    _bridge_all_envs()
    try:
        return _lifecycle_preflight_upload_disk(temp_dir, estimated_bytes)
    except RuntimeError as exc:
        msg = str(exc).replace("RUNPOD_LIFECYCLE_UPLOAD_TMPDIR", "VIBECOMFY_UPLOAD_TMPDIR")
        raise RuntimeError(msg) from None


def _compat_guard_factory(base_factory: Any) -> Any:
    """Wrap *base_factory* so returned guard always has breach_log + attach."""

    class _GuardAdapter:
        def __init__(self, factory: Any) -> None:
            self._factory = factory

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            guard = self._factory(*args, **kwargs)
            if not hasattr(guard, "breach_log"):
                guard.breach_log = []  # type: ignore[attr-defined]
            if not hasattr(guard, "attach"):
                guard.attach = lambda _pod: None  # type: ignore[attr-defined]
            return guard

    return _GuardAdapter(base_factory)


async def run_pod(
    remote_script: str,
    *,
    name_prefix: str,
    exclude: set[str],
    upload_mode: Literal["sftp_walk", "tarball"] = "sftp_walk",
    timeout: int,
) -> int:
    """Launch a pod, ship vibecomfy, run *remote_script* synchronously.

    Thin wrapper around :func:`runpod_lifecycle.runner.ship_and_run`.
    """
    # install_signal_handlers must be called in SHIM namespace (L213 monkeypatch)
    install_signal_handlers(asyncio.get_running_loop())

    _bridge_all_envs()
    config = RunPodConfig.from_env(**_runpod_config_kwargs())

    # guard_factory resolved at CALL SITE (runtime lookup of module-level
    # ``PodGuard``) so monkeypatching in tests works.
    result = await ship_and_run(
        config,
        remote_script,
        local_root=ROOT,
        remote_root=REMOTE_ROOT,
        exclude=exclude,
        upload_mode=upload_mode,
        timeout=timeout,
        name_prefix=name_prefix,
        terminate_after_exec=True,
        guard_factory=_compat_guard_factory(PodGuard),
    )

    print(result.stdout, flush=True)
    if result.stderr.strip():
        print(result.stderr, flush=True)

    if result.artifact_root is not None:
        _finalize_artifacts(
            result.artifact_root,
            pod_id=getattr(result.pod, "id", None) if result.pod else None,
            exit_code=result.returncode,
            terminated=result.terminated,
            remote_command=remote_script,
            upload=result.upload_info,
        )
        _print_detached_summary(
            pod_id=getattr(result.pod, "id", None) if result.pod else None,
            exit_code=result.returncode,
            terminated=result.terminated,
            artifact_root=result.artifact_root,
        )

    return result.returncode


async def run_pod_detached(
    remote_script: str,
    *,
    name_prefix: str,
    exclude: set[str],
    upload_mode: Literal["sftp_walk", "tarball"] = "sftp_walk",
    timeout: int,
    poll_interval: int = 60,
    artifact_root_out: list[Path | None] | None = None,
) -> int:
    """Launch, run, download, and finalise one isolated detached invocation.

    The lifecycle package uses ``local_root / "artifacts"`` as its download
    destination. This wrapper gives every call a private snapshot root, binds
    only that root's returned download, and removes the snapshot in ``finally``
    on success, error, or cancellation.
    """
    install_signal_handlers(asyncio.get_running_loop())

    _bridge_all_envs()
    config = RunPodConfig.from_env(**_runpod_config_kwargs())
    staging_root = _stage_lifecycle_local_root(exclude)
    try:
        artifact_root = _allocate_artifact_root()
        current_artifact_root: Path | None = None
        result = await ship_and_run_detached(
            config,
            remote_script,
            local_root=staging_root,
            remote_root=REMOTE_ROOT,
            exclude=exclude,
            upload_mode=upload_mode,
            timeout=timeout,
            name_prefix=name_prefix,
            terminate_after_exec=True,
            poll_interval=poll_interval,
        )
        current_artifact_root = _bind_artifact_root(
            result.artifact_root,
            artifact_root,
            staging_root=staging_root,
        )
        pod_id = getattr(result.pod, "id", None) if result.pod else None
        if current_artifact_root is not None:
            _finalize_artifacts(
                current_artifact_root,
                pod_id=pod_id,
                exit_code=result.returncode,
                terminated=result.terminated,
                remote_command=_lifecycle_detached_remote_contract(),
                upload=result.upload_info,
            )
        _print_detached_summary(
            pod_id=pod_id,
            exit_code=result.returncode,
            terminated=result.terminated,
            artifact_root=current_artifact_root,
        )
        if artifact_root_out is not None:
            artifact_root_out.append(current_artifact_root)
        return result.returncode
    finally:
        _cleanup_lifecycle_local_root(staging_root)
