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
import sys
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/workspace/vibecomfy"
MiB = 1024 * 1024

DEFAULT_UPLOAD_EXCLUDES: set[str] = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".desloppify", ".megaplan",
    "out", "output", "vendor", "ready_templates/sources", "custom_nodes", "input",
    "node_modules", ".mypy_cache", ".ruff_cache", ".DS_Store",
}

VIBECOMFY_RUNPOD_DISK_SIZE_ENV = "VIBECOMFY_RUNPOD_DISK_SIZE_GB"
VIBECOMFY_RUNPOD_CONTAINER_DISK_ENV = "VIBECOMFY_RUNPOD_CONTAINER_DISK_GB"


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
from runpod_lifecycle import UploadHeartbeat  # noqa: E402
from runpod_lifecycle import install_signal_handlers  # noqa: E402
from runpod_lifecycle import should_skip  # noqa: E402
from runpod_lifecycle import RunPodConfig  # noqa: E402
from runpod_lifecycle.config import _parse_gpu_type_env  # noqa: E402
from runpod_lifecycle import ship_and_run  # noqa: E402
from runpod_lifecycle import ship_and_run_detached  # noqa: E402
from runpod_lifecycle import ShipAndRunResult  # noqa: E402
from runpod_lifecycle import _build_upload_tarball as _lifecycle_build_upload_tarball  # noqa: E402
from runpod_lifecycle import _preflight_upload_disk as _lifecycle_preflight_upload_disk  # noqa: E402

from scripts.runpod_artifacts import _parse_tsv  # noqa: E402
from scripts.runpod_artifacts import _png_info  # noqa: E402
from scripts.runpod_artifacts import _finalize_artifacts  # noqa: E402
from scripts.runpod_artifacts import _build_artifact_manifest  # noqa: E402
from scripts.runpod_artifacts import _print_detached_summary  # noqa: E402

_ENV_BRIDGE_MAP: dict[str, str] = {
    "VIBECOMFY_UPLOAD_TMPDIR": "RUNPOD_LIFECYCLE_UPLOAD_TMPDIR",
    "VIBECOMFY_UPLOAD_MIN_FREE_BYTES": "RUNPOD_LIFECYCLE_UPLOAD_MIN_FREE_BYTES",
    "VIBECOMFY_UPLOAD_PROGRESS_SECONDS": "RUNPOD_LIFECYCLE_UPLOAD_PROGRESS_SECONDS",
    "VIBECOMFY_UPLOAD_PROGRESS_FILES": "RUNPOD_LIFECYCLE_UPLOAD_PROGRESS_FILES",
}


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
    """Launch a pod, ship vibecomfy, run *remote_script* detached, poll,
    download artifacts, and finalise.

    Thin wrapper around
    :func:`runpod_lifecycle.runner.ship_and_run_detached` with
    vibecomfy-specific polling targets and artifact paths.

    When supplied, ``artifact_root_out`` receives the exact local artifact
    root returned by this invocation, so callers can bind post-processing to
    their own run without guessing from shared artifact directories.
    """
    install_signal_handlers(asyncio.get_running_loop())

    _bridge_all_envs()
    config = RunPodConfig.from_env(**_runpod_config_kwargs())

    poll_command_template = (
        f"cd {REMOTE_ROOT}\n"
        'echo "=== POLL $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="\n'
        "if [ -f out/corpus_matrix/results.tsv ]; then "
        'echo "--- RESULTS ---"; cat out/corpus_matrix/results.tsv; fi\n'
        "if [ -f out/corpus_matrix/ready_results.tsv ]; then "
        'echo "--- READY ---"; cat out/corpus_matrix/ready_results.tsv; fi\n'
        'echo "--- MEDIA ---"\n'
        "find out/corpus_matrix output -maxdepth 5 -type f "
        "\\( -name '*.png' -o -name '*.mp4' -o -name '*.webp' "
        "-o -name '*.webm' \\) "
        "-printf '%TY-%Tm-%Td %TH:%TM %s %p\\n' 2>/dev/null | sort | tail -80\n"
        'echo "--- LOG ---"\n'
        "tail -80 /tmp/vibecomfy-remote-live.log 2>/dev/null || true\n"
        "tail -80 out/corpus_matrix/live.log 2>/dev/null || true\n"
        'echo "--- EXIT ---"\n'
        "cat {poll_exit_marker} 2>/dev/null || true\n"
    )

    result = await ship_and_run_detached(
        config,
        remote_script,
        local_root=ROOT,
        remote_root=REMOTE_ROOT,
        exclude=exclude,
        upload_mode=upload_mode,
        timeout=timeout,
        name_prefix=name_prefix,
        terminate_after_exec=True,
        poll_interval=poll_interval,
    )

    pod_id = getattr(result.pod, "id", None) if result.pod else None
    _finalize_artifacts(
        result.artifact_root,
        pod_id=pod_id,
        exit_code=result.returncode,
        terminated=result.terminated,
        remote_command=poll_command_template,
        upload=result.upload_info,
    )
    _print_detached_summary(
        pod_id=pod_id,
        exit_code=result.returncode,
        terminated=result.terminated,
        artifact_root=result.artifact_root,
    )
    if artifact_root_out is not None:
        artifact_root_out.append(result.artifact_root)

    return result.returncode
