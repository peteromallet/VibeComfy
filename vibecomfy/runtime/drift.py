"""Drift detection for custom-node pins and ComfyUI commit.

Provides :func:`collect_drift` which compares pinned template requirements
against the installed pack state (lockfile, git HEAD, schema hashes) and
optionally checks the ComfyUI git HEAD against a template-pinned commit.

Per-process caching via a module-level dict keyed on ``(lockfile_mtime,
workflow_id)`` keeps repeated calls cheap while staying responsive to
lockfile updates within the same process lifetime.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Any

from vibecomfy.errors import DriftError
from vibecomfy.workflow import VibeWorkflow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-process cache — keyed by (lockfile_mtime, workflow_id) → structured dict
# ---------------------------------------------------------------------------
_drift_cache: dict[tuple[float, str], dict[str, Any]] = {}


def _cache_key(workflow: VibeWorkflow) -> tuple[float, str]:
    """Return a stable cache key for the current process lifetime.

    Uses lockfile mtime (so lockfile edits are detected even without
    restarting) and workflow id.
    """
    lock_path = Path("custom_nodes.lock")
    mtime = lock_path.stat().st_mtime if lock_path.is_file() else 0.0
    return (mtime, workflow.id)


def collect_drift(workflow: VibeWorkflow) -> dict[str, Any]:
    """Return a structured drift report for *workflow*.

    The returned dict has three top-level keys:

    ``pinned``
        What the template declares or requires (custom_node_packs,
        lockfile entries, optional ``comfy_commit``).
    ``actual``
        What is observed on disk (installed pack git HEADs, schema
        hashes, ComfyUI git HEAD if applicable).
    ``mismatches``
        List of human-readable mismatch descriptions.

    Results are cached per-process; repeated calls with the same
    workflow id and lockfile mtime return the same dict instance.

    The function never raises — even when the lockfile is missing.  Callers
    that want hard failure on mismatch should check ``mismatches`` and raise
    :class:`DriftError` themselves.
    """
    key = _cache_key(workflow)
    cached = _drift_cache.get(key)
    if cached is not None:
        return cached

    pinned: dict[str, Any] = {}
    actual: dict[str, Any] = {}
    mismatches: list[str] = []

    # -- (a) custom_node_packs drift ------------------------------------------
    _collect_nodepack_drift(workflow, pinned, actual, mismatches)

    # -- (b) comfy_commit drift -----------------------------------------------
    _collect_comfy_commit_drift(workflow, pinned, actual, mismatches)

    result: dict[str, Any] = {
        "pinned": pinned,
        "actual": actual,
        "mismatches": mismatches,
    }
    _drift_cache[key] = result

    if mismatches:
        for m in mismatches:
            logger.warning("vibecomfy drift: %s", m)

    return result


def _invalidate_cache_entry(workflow: VibeWorkflow) -> None:
    """Remove cached drift results for *workflow* (useful for tests)."""
    key = _cache_key(workflow)
    _drift_cache.pop(key, None)


# ---------------------------------------------------------------------------
# (a) custom_node_packs drift
# ---------------------------------------------------------------------------


def _collect_nodepack_drift(
    workflow: VibeWorkflow,
    pinned: dict[str, Any],
    actual: dict[str, Any],
    mismatches: list[str],
) -> None:
    """Compare template-pinned packs against installed state."""
    from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile

    lock_entries: list[LockEntry] = read_lockfile()
    pinned["custom_node_packs"] = list(workflow.requirements.custom_nodes)
    pinned["lockfile_entries"] = {
        entry.name: {
            "git_commit_sha": entry.git_commit_sha,
            "url": entry.url,
            "source_sha256": dict(entry.source_sha256),
            "schema_hash": entry.schema_hash,
            "class_schema_sha256": entry.class_schema_sha256,
        }
        for entry in lock_entries
    }

    if not lock_entries:
        actual["custom_node_packs"] = "lockfile not found"
        return

    actual_packs: dict[str, Any] = {}
    for entry in lock_entries:
        pack_info: dict[str, Any] = {
            "name": entry.name,
            "pinned_git_commit_sha": entry.git_commit_sha,
        }
        pack_dir = _nodepack_dir(entry.name)
        if pack_dir is None:
            pack_info["installed_git_head"] = None
            pack_info["warning"] = f"{entry.name} in lockfile but not installed"
            actual_packs[entry.name] = pack_info
            continue

        git_head = _git_head(pack_dir)
        pack_info["installed_git_head"] = git_head
        pack_info["pack_dir"] = str(pack_dir)

        if git_head is None:
            pack_info["warning"] = (
                f"{entry.name} installed at {pack_dir} but git HEAD unreadable"
            )
            actual_packs[entry.name] = pack_info
            continue

        if git_head != entry.git_commit_sha:
            mismatches.append(
                f"{entry.name} git HEAD {git_head} does not match "
                f"lockfile git_commit_sha {entry.git_commit_sha}"
            )
            pack_info["git_mismatch"] = True

        # Schema hash drift
        if entry.schema_hash is not None or entry.class_schema_sha256 is not None:
            pinned_hash = entry.schema_hash or entry.class_schema_sha256
            pack_info["pinned_schema_hash"] = pinned_hash
            actual_hash = _compute_pack_schema_hash(entry, pack_dir)
            pack_info["actual_schema_hash"] = actual_hash
            if actual_hash is not None and pinned_hash is not None and actual_hash != pinned_hash:
                mismatches.append(
                    f"{entry.name} schema hash {actual_hash} does not match "
                    f"pinned {pinned_hash}"
                )
                pack_info["schema_mismatch"] = True

        # Source file sha256 drift (reuse doctor.py pattern)
        for rel_path, expected_hash in entry.source_sha256.items():
            source_path = pack_dir / rel_path
            key = f"source:{rel_path}"
            pack_info.setdefault("source_checks", {})[key] = {
                "expected": expected_hash,
            }
            if not source_path.is_file():
                mismatches.append(
                    f"{entry.name} source {rel_path} is missing; "
                    f"expected sha256 {expected_hash}"
                )
                pack_info["source_checks"][key]["actual"] = None
                pack_info["source_checks"][key]["missing"] = True
                continue
            actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            pack_info["source_checks"][key]["actual"] = actual_hash
            if actual_hash != expected_hash:
                mismatches.append(
                    f"{entry.name} source {rel_path} sha256 {actual_hash} "
                    f"does not match lockfile {expected_hash}"
                )
                pack_info["source_checks"][key]["mismatch"] = True

        actual_packs[entry.name] = pack_info

    actual["custom_node_packs"] = actual_packs


# ---------------------------------------------------------------------------
# (b) comfy_commit drift
# ---------------------------------------------------------------------------


def _collect_comfy_commit_drift(
    workflow: VibeWorkflow,
    pinned: dict[str, Any],
    actual: dict[str, Any],
    mismatches: list[str],
) -> None:
    """Compare template-pinned ``comfy_commit`` against installed ComfyUI."""
    metadata = workflow.metadata if isinstance(workflow.metadata, dict) else {}
    pinned_commit: str | None = None
    raw = metadata.get("comfy_commit")
    if isinstance(raw, str) and raw:
        pinned_commit = raw
    pinned["comfy_commit"] = pinned_commit

    installed_commit = _comfyui_git_head()
    actual["comfy_commit"] = installed_commit

    if pinned_commit is not None and installed_commit is not None:
        if pinned_commit != installed_commit:
            mismatches.append(
                f"ComfyUI commit {installed_commit} does not match "
                f"pinned {pinned_commit}"
            )


# ---------------------------------------------------------------------------
# Filesystem / git helpers (reuse doctor.py patterns)
# ---------------------------------------------------------------------------


def _nodepack_dir(name: str) -> Path | None:
    """Find the on-disk directory for a custom node pack, if installed."""
    candidates = (
        Path("vendor") / name,
        Path("custom_nodes") / name,
        Path("vendor") / "ComfyUI" / "custom_nodes" / name,
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _git_head(pack_dir: Path) -> str | None:
    """Return the git HEAD SHA of *pack_dir*, or ``None`` on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _comfyui_git_head() -> str | None:
    """Return the git HEAD SHA of the installed ComfyUI, or ``None``."""
    # Try common ComfyUI locations
    candidates = (
        Path("vendor/ComfyUI"),
        Path("ComfyUI"),
    )
    for candidate in candidates:
        if (candidate / ".git").is_dir():
            return _git_head(candidate)
    return None


def _compute_pack_schema_hash(
    entry: Any,  # LockEntry
    pack_dir: Path,
) -> str | None:
    """Compute a best-effort schema hash for an installed pack.

    Looks for ``*.py`` files in the pack directory (excluding ``__pycache__``)
    and hashes their combined content. This is a heuristic; the lockfile's
    ``schema_hash`` / ``class_schema_sha256`` fields are the authoritative
    source.
    """
    try:
        sha = hashlib.sha256()
        py_files = sorted(
            p for p in pack_dir.rglob("*.py")
            if "__pycache__" not in str(p)
        )
        if not py_files:
            return None
        for py_path in py_files:
            sha.update(py_path.read_bytes())
        return sha.hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# strict-drift gate — called before queue boundaries
# ---------------------------------------------------------------------------


def enforce_strict_drift(workflow: VibeWorkflow) -> None:
    """Collect drift and raise :class:`DriftError` if any mismatches exist.

    This is the pre-queue gate wired into all session paths when
    ``SessionConfig.strict_drift`` is ``True``.
    """
    drift = collect_drift(workflow)
    mismatches: list[str] = drift.get("mismatches", [])
    if mismatches:
        raise DriftError(
            "Pre-queue drift check failed:\n  - "
            + "\n  - ".join(mismatches),
            next_action="vibecomfy runtime doctor",
        )
