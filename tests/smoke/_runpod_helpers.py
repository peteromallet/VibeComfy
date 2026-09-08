"""Shared helpers for opt-in RunPod smoke tests.

Centralises the bits every test in tests/smoke/test_*runpod*.py needs:
  * loading the runpod_lifecycle package (with VIBECOMFY_RUNPOD_LIFECYCLE_ROOT fallback)
  * resolving the git repo URL + ref to install on a remote pod
  * installing the current branch onto a pod via SSH
  * a single canonical pod-name pattern so orphans are greppable
  * a session-scoped budget cap (``VIBECOMFY_RUNPOD_BUDGET_USD``) enforced via
    ``launch_with_budget`` — projects spend before launch, settles actuals on
    termination, and ``pytest.fail``s before the over-budget pod is provisioned.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import subprocess
import sys
import time
from types import ModuleType
from typing import Any

import pytest


POD_NAME_PREFIX = "vibecomfy-layer2"


# Per-GPU hourly USD rates. Source: runpod.io community-cloud pricing
# (https://www.runpod.io/pricing) — kept hand-curated so an unfamiliar GPU type
# raises rather than silently being charged at the wrong rate.
HOURLY_USD: dict[str, float] = {
    "NVIDIA GeForce RTX 4090": 0.69,
    # RunPod's current catalog fixture for the 32-GB Blackwell 5090. Keep
    # this explicit so the budget gate cannot silently price an unknown GPU.
    "NVIDIA GeForce RTX 5090": 0.95,
    "NVIDIA RTX A6000": 0.79,
    "NVIDIA A100 80GB PCIe": 1.89,
    "NVIDIA A100-SXM4-80GB": 1.99,
}


_BUDGET_STATE: dict[str, Any] = {
    "projected_usd": 0.0,
    "actual_usd": 0.0,
    "budget_usd": None,
}


_PYTEST_CONFIG: pytest.Config | None = None


def set_pytest_config(config: pytest.Config | None) -> None:
    """Stash the active pytest config so budget helpers can resolve defaults."""
    global _PYTEST_CONFIG
    _PYTEST_CONFIG = config


def get_budget_state() -> dict[str, Any]:
    """Return a snapshot of the running budget tally (read-only)."""
    return dict(_BUDGET_STATE)


def reset_budget_state() -> None:
    _BUDGET_STATE["projected_usd"] = 0.0
    _BUDGET_STATE["actual_usd"] = 0.0
    _BUDGET_STATE["budget_usd"] = None


def _hourly_rate(gpu_type: str) -> float:
    try:
        return HOURLY_USD[gpu_type]
    except KeyError as exc:
        raise RuntimeError(
            f"unknown gpu_type for budget cap: {gpu_type!r}; add it to HOURLY_USD with the runpod.io price."
        ) from exc


def _resolve_budget(pytestconfig: pytest.Config | None = None) -> float:
    """Return the active budget in USD, honouring env override, falling back to flag-derived defaults."""
    cached = _BUDGET_STATE.get("budget_usd")
    if cached is not None:
        return float(cached)
    raw = os.environ.get("VIBECOMFY_RUNPOD_BUDGET_USD")
    if raw:
        try:
            value = float(raw)
        except ValueError as exc:
            raise RuntimeError(
                f"VIBECOMFY_RUNPOD_BUDGET_USD={raw!r} is not a valid float."
            ) from exc
    else:
        config = pytestconfig if pytestconfig is not None else _PYTEST_CONFIG
        runpod_full = bool(config.getoption("--runpod-full")) if config is not None else False
        value = 15.0 if runpod_full else 2.0
    _BUDGET_STATE["budget_usd"] = value
    return value


def precharge_budget(
    pytestconfig: pytest.Config | None = None,
    *,
    gpu_type: str,
    max_runtime_seconds: int,
) -> float:
    """Project spend for a pending pod launch and fail before going over budget.

    Returns the projected USD cost added to the in-flight tally.
    """
    rate = _hourly_rate(gpu_type)
    projected = (max_runtime_seconds / 3600.0) * rate
    budget = _resolve_budget(pytestconfig)
    cumulative = _BUDGET_STATE["actual_usd"] + _BUDGET_STATE["projected_usd"] + projected
    if cumulative > budget:
        pytest.fail(
            f"RunPod budget exceeded: this launch would bring projected spend to "
            f"${cumulative:.2f} (actual ${_BUDGET_STATE['actual_usd']:.2f} + "
            f"in-flight ${_BUDGET_STATE['projected_usd']:.2f} + new ${projected:.2f}) "
            f"vs budget ${budget:.2f}. Set VIBECOMFY_RUNPOD_BUDGET_USD to raise the cap."
        )
    _BUDGET_STATE["projected_usd"] += projected
    return projected


def settle_budget(
    *,
    gpu_type: str,
    elapsed_seconds: float,
    projected_seconds: int,
) -> None:
    """Move spend from projected to actual once a pod terminates."""
    rate = _hourly_rate(gpu_type)
    projected = (projected_seconds / 3600.0) * rate
    actual = (max(0.0, elapsed_seconds) / 3600.0) * rate
    _BUDGET_STATE["projected_usd"] = max(0.0, _BUDGET_STATE["projected_usd"] - projected)
    _BUDGET_STATE["actual_usd"] += actual


def require_runpod_api_key() -> None:
    """Skip the calling test if RUNPOD_API_KEY is not set."""
    if not os.environ.get("RUNPOD_API_KEY"):
        pytest.skip("RUNPOD_API_KEY is required for the opt-in RunPod smoke test.")


def load_runpod_lifecycle() -> ModuleType:
    """Import runpod_lifecycle, honouring VIBECOMFY_RUNPOD_LIFECYCLE_ROOT for source checkouts."""
    lifecycle_root = os.environ.get("VIBECOMFY_RUNPOD_LIFECYCLE_ROOT")
    if lifecycle_root and lifecycle_root not in sys.path:
        sys.path.insert(0, lifecycle_root)
    try:
        return importlib.import_module("runpod_lifecycle")
    except ImportError:
        pytest.skip(
            "runpod_lifecycle is required; install it or set VIBECOMFY_RUNPOD_LIFECYCLE_ROOT to its source root."
        )
        raise  # unreachable; appeases type checkers


def pod_name(phase: str, family: str = "all") -> str:
    """Canonical name pattern: vibecomfy-layer2-{phase}-{family}-{epoch}."""
    return f"{POD_NAME_PREFIX}-{phase}-{family}-{int(time.time())}"


def resolve_repo_install_target() -> tuple[str, str]:
    """Return (repo_url, git_ref) for `pip install git+{url}@{ref}`.

    Skips the test when the repo URL cannot be resolved (no env var, no git remote).
    """
    repo_url = os.environ.get("VIBECOMFY_RUNPOD_REPO_URL") or _git_output("config --get remote.origin.url")
    if not repo_url:
        pytest.skip("Set VIBECOMFY_RUNPOD_REPO_URL or configure git remote.origin.url for remote install.")
    git_ref = os.environ.get("VIBECOMFY_RUNPOD_GIT_REF") or _git_output("rev-parse --abbrev-ref HEAD") or "HEAD"
    if git_ref == "HEAD":
        git_ref = _git_output("rev-parse HEAD") or "HEAD"
    return repo_url, git_ref


async def install_current_branch(pod, *, retries: int = 3) -> None:
    """Clone vibecomfy + install HiddenSwitch ComfyUI onto a ready pod.

    A ``pip install git+...`` wheel is not enough: ``ready_templates/`` lives at the
    repo root and is not shipped with the wheel; ``vibecomfy.registry.ready`` resolves
    it from ``Path(__file__).parents[2]/'ready_templates'``, which only exists in a
    checked-out repo. Mirrors ``scripts/runpod_validate.py``.

    Retries the bash install up to ``retries`` times with backoff: RunPod's shared
    ``/workspace`` volume occasionally races on pack download (``tmp_pack_*: No such
    file or directory``) or post-clone checkout (``unable to create file
    requirements.txt``). A clean ``rm -rf`` between tries recovers from both.
    """
    repo_url, git_ref = resolve_repo_install_target()
    # Install onto container-local disk (/root) instead of the shared /workspace
    # network volume — `/workspace` is persistent across pod instances so prior
    # failed installs leave corrupt directories that defeat `rm -rf` on the next
    # pod (`Directory not empty`, stale .git/hooks symlinks, etc).
    repo_dir = "/root/vibecomfy"
    # --depth=1 + shallow-submodules keeps the transfer small enough that pack-write
    # races are far less likely; we don't need history for an ephemeral install.
    install_cmd = (
        "set -e && "
        f"rm -rf {repo_dir} 2>/dev/null || true && "
        f"git clone --depth=1 --branch {git_ref} --shallow-submodules --recurse-submodules "
        f"{repo_url} {repo_dir} && "
        f"cd {repo_dir} && "
        "python -m pip install --upgrade pip && "
        "python -m pip install "
        "'comfyui@git+https://github.com/peteromallet/ComfyUI.git@fix/latentupscale-model-mmap-residency' "
        "'comfy-script[default]' && "
        "python -m pip install -e ."
    )
    last_err: tuple[int, str, str] | None = None
    for attempt in range(1, retries + 1):
        code, stdout, stderr = await pod.exec_ssh(install_cmd, timeout=1800)
        if code == 0:
            return
        last_err = (code, stdout, stderr)
        if attempt < retries:
            await asyncio.sleep(min(15 * attempt, 60))
    assert last_err is not None
    code, stdout, stderr = last_err
    raise AssertionError(
        f"remote install failed with {code} after {retries} attempts\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


async def ensure_node_packs(
    pod, template_ids: tuple[str, ...] | list[str], *, timeout: int = 1200
) -> None:
    """Install custom-node packs declared by each template's applicable patches.

    Loads each template on the pod, runs ``find_applicable`` + ``patch.apply``
    so ``ensure_custom_nodes`` populates ``workflow.requirements.custom_nodes``,
    then ``install_pack(name=...)`` for the union. Packs land in
    ``/root/vibecomfy/custom_nodes/``, which matches
    ``comfy.cmd.folder_paths.base_path`` when ComfyUI is started from there —
    so the embedded session picks them up on first ``start()``.

    Forces ``install_pack``'s git-clone path: cm-cli (which ``install_pack``
    prefers when present) demands a real ComfyUI repo checkout via
    ``COMFYUI_PATH``, but ComfyUI is pip-installed on the pod and has no such
    checkout. cm-cli would fail with ``'{comfy_path}' is not a valid
    'COMFYUI_PATH' location.``; the clone path works without that env var.
    """
    if not template_ids:
        return
    cmd = (
        "set -e && cd /root/vibecomfy && python - <<'PY'\n"
        "from __future__ import annotations\n"
        "\n"
        "import sys\n"
        "\n"
        "from vibecomfy import load_workflow_any\n"
        "from vibecomfy.node_packs import install_pack\n"
        "from vibecomfy.patches.registry import find_applicable\n"
        "\n"
        f"TEMPLATE_IDS = {tuple(template_ids)!r}\n"
        "\n"
        "needed: set[str] = set()\n"
        "for tid in TEMPLATE_IDS:\n"
        "    wf = load_workflow_any(tid)\n"
        "    for patch in find_applicable(wf):\n"
        "        patch.apply(wf)\n"
        "    declared = list(getattr(getattr(wf, 'requirements', None), 'custom_nodes', None) or ())\n"
        "    print(f'  declared by {tid}: {declared}')\n"
        "    needed.update(declared)\n"
        "\n"
        "if not needed:\n"
        "    print('VIBECOMFY_NODES_ENSURE_OK: no packs declared')\n"
        "    sys.exit(0)\n"
        "\n"
        "no_cm_cli = lambda install_root, runner: None\n"
        "failed: list[tuple[str, str, str | None]] = []\n"
        "for name in sorted(needed):\n"
        "    result = install_pack(name=name, cm_cli_resolver=no_cm_cli)\n"
        "    sha = f' {result.git_commit_sha}' if result.git_commit_sha else ''\n"
        "    print(f'  install_pack {name}: {result.status}{sha}')\n"
        "    if result.error:\n"
        "        print(f'    error: {result.error}')\n"
        "    if result.status not in ('installed', 'refreshed'):\n"
        "        failed.append((name, result.status, result.error))\n"
        "\n"
        "if failed:\n"
        "    print('VIBECOMFY_NODES_ENSURE_FAIL=' + repr(failed))\n"
        "    sys.exit(1)\n"
        "print('VIBECOMFY_NODES_ENSURE_OK')\n"
        "PY"
    )
    code, stdout, stderr = await pod.exec_ssh(cmd, timeout=timeout)
    if code != 0:
        raise AssertionError(
            f"node-pack ensure failed code={code}\n"
            f"templates={list(template_ids)}\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )


async def launch_with_retry(
    runpod_lifecycle, config, name: str, *, retries: int = 4
):
    """Launch a pod, retrying transient RunPod ``LaunchFailure`` with backoff.

    RunPod returns 'Something went wrong. Please try again later or contact support.'
    or 'This machine does not have the resources to deploy your pod.' for ~50% of
    4090 launches when capacity is thin. Retry covers transient capacity windows.
    """
    LaunchFailure = runpod_lifecycle.LaunchFailure  # type: ignore[attr-defined]
    last_exc: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            return await runpod_lifecycle.launch(config, name=name)
        except LaunchFailure as exc:
            last_exc = exc
            if attempt < retries:
                # 30s, 60s, 90s, ... — RunPod capacity windows recover on tens-of-seconds.
                await asyncio.sleep(30 * attempt)
    assert last_exc is not None
    raise last_exc


@contextlib.asynccontextmanager
async def launch_with_budget(
    runpod_lifecycle,
    config,
    *,
    name: str,
    max_runtime_seconds: int,
    retries: int = 4,
    pytestconfig: pytest.Config | None = None,
):
    """Async context manager: precharge budget, launch (with retry), settle and terminate.

    Yields the launched pod. Always tears the pod down on exit and reconciles
    the actual elapsed cost against the precharged projection.
    """
    gpu_type = config.gpu_type
    precharge_budget(pytestconfig, gpu_type=gpu_type, max_runtime_seconds=max_runtime_seconds)
    start = time.monotonic()
    pod = await launch_with_retry(runpod_lifecycle, config, name, retries=retries)
    try:
        yield pod
    finally:
        elapsed = time.monotonic() - start
        try:
            await pod.terminate()
        finally:
            settle_budget(
                gpu_type=gpu_type,
                elapsed_seconds=elapsed,
                projected_seconds=max_runtime_seconds,
            )


def _git_output(args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args.split()],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


__all__ = [
    "HOURLY_USD",
    "POD_NAME_PREFIX",
    "ensure_node_packs",
    "get_budget_state",
    "install_current_branch",
    "launch_with_budget",
    "launch_with_retry",
    "load_runpod_lifecycle",
    "pod_name",
    "precharge_budget",
    "require_runpod_api_key",
    "reset_budget_state",
    "resolve_repo_install_target",
    "set_pytest_config",
    "settle_budget",
]
