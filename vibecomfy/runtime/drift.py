"""Drift detection for custom-node pins and ComfyUI commit.

Provides :func:`collect_drift` which compares pinned template requirements
against the installed pack state (lockfile, git HEAD, schema hashes) and
optionally checks the ComfyUI git HEAD against a template-pinned commit.

Per-process caching via a module-level dict keyed on ``(lockfile_mtime,
workflow_id)`` keeps repeated calls cheap while staying responsive to
lockfile updates within the same process lifetime.
"""

from __future__ import annotations

import logging
import hashlib
import subprocess
from pathlib import Path
from typing import Any

from vibecomfy.errors import DriftError
from vibecomfy.node_packs import compute_schema_hash, resolve_lockfile_path
from vibecomfy.workflow import VibeWorkflow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-process cache — keyed by (lockfile_path, lockfile_mtime, workflow_id)
# ---------------------------------------------------------------------------
_drift_cache: dict[tuple[Any, ...], dict[str, Any]] = {}


def _has_custom_node_requirements(workflow: VibeWorkflow) -> bool:
    """Return whether *workflow* declares any custom-node pack."""
    requirements = getattr(workflow, "requirements", None)
    return bool(
        getattr(requirements, "custom_nodes", ())
        or getattr(requirements, "custom_node_refs", ())
    )



def _cache_key(workflow: VibeWorkflow, lockfile_path: str | Path | None = None) -> tuple[Any, ...]:
    """Return a stable cache key for the current process lifetime.

    Uses resolved lockfile path and mtime (so alternate explicit lockfiles and
    lockfile edits are detected without restarting), plus workflow id.
    """
    lock_path = resolve_lockfile_path(lockfile_path)
    mtime = lock_path.stat().st_mtime if lock_path.is_file() else 0.0
    semantic_digest = getattr(workflow, "semantic_digest", None)
    digest = semantic_digest() if callable(semantic_digest) else None
    observed: list[tuple[Any, ...]] = []
    try:
        from vibecomfy.custom_node_refs import effective_lock_entries
        from vibecomfy.node_packs import read_lockfile
        for entry in effective_lock_entries(workflow, read_lockfile(lock_path)):
            directory = _nodepack_dir(entry.name)
            source_state: list[tuple[str, str | None]] = []
            if directory is not None:
                for rel_path in sorted(entry.source_sha256):
                    source_path = directory / rel_path
                    digest = (
                        hashlib.sha256(source_path.read_bytes()).hexdigest()
                        if source_path.is_file() else None
                    )
                    source_state.append((rel_path, digest))
            schema_state = _canonical_pack_schema_hash(entry)
            observed.append(
                (
                    entry.name,
                    _git_head(directory) if directory else None,
                    _git_origin(directory) if directory else None,
                    tuple(source_state),
                    schema_state.get("hash"),
                    schema_state.get("status"),
                )
            )
    except Exception:
        observed.append(("__unverified__", None))
    return (str(lock_path.resolve()), mtime, workflow.id, digest, tuple(observed))


def collect_drift(
    workflow: VibeWorkflow, *, lockfile_path: str | Path | None = None
) -> dict[str, Any]:
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
    workflow id, lockfile path, and lockfile mtime return the same dict instance.

    The function never raises — even when the lockfile is missing.  Callers
    that want hard failure on mismatch should check ``mismatches`` and raise
    :class:`DriftError` themselves.
    """
    key = _cache_key(workflow, lockfile_path)
    cached = _drift_cache.get(key)
    if cached is not None:
        return cached

    pinned: dict[str, Any] = {}
    actual: dict[str, Any] = {}
    mismatches: list[str] = []

    # -- (a) custom_node_packs drift ------------------------------------------
    _collect_nodepack_drift(workflow, pinned, actual, mismatches, lockfile_path=lockfile_path)

    # -- (b) comfy_commit drift -----------------------------------------------
    _collect_comfy_commit_drift(workflow, pinned, actual, mismatches)

    from vibecomfy.runtime.dependencies import compare_runtime, runtime_requirements_from_workflow
    runtime_requirements = runtime_requirements_from_workflow(workflow)
    result: dict[str, Any] = {
        "pinned": pinned,
        "actual": actual,
        "mismatches": mismatches,
    }
    if runtime_requirements is not None:
        result["runtime"] = compare_runtime(runtime_requirements)
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
    *,
    lockfile_path: str | Path | None = None,
) -> None:
    """Compare template-pinned packs against installed state."""
    from vibecomfy.node_packs import LockEntry, read_lockfile
    from vibecomfy.custom_node_refs import effective_lock_entries

    lock_entries: list[LockEntry] = effective_lock_entries(
        workflow, read_lockfile(resolve_lockfile_path(lockfile_path))
    )
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
            pack_info["status"] = "unverified"
            pack_info["warning"] = f"{entry.name} in requirements is not installed"
            mismatches.append(f"{entry.name} installed checkout is unavailable; installation state is unverified")
            actual_packs[entry.name] = pack_info
            continue

        git_head = _git_head(pack_dir)
        pack_info["installed_git_head"] = git_head
        pack_info["pack_dir"] = str(pack_dir)

        if git_head is None:
            pack_info["status"] = "unverified"
            pack_info["warning"] = (
                f"{entry.name} installed at {pack_dir} but git HEAD unreadable"
            )
            actual_packs[entry.name] = pack_info
            continue

        origin = _git_origin(pack_dir)
        pack_info["installed_origin"] = origin
        if entry.url and origin and origin.rstrip("/") != entry.url.rstrip("/"):
            mismatches.append(f"{entry.name} origin {origin} does not match declared {entry.url}")
            pack_info["origin_mismatch"] = True

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
            schema_check = _canonical_pack_schema_hash(entry)
            pack_info["schema_hash_status"] = schema_check["status"]
            if schema_check.get("reason"):
                pack_info["schema_hash_reason"] = schema_check["reason"]
            actual_hash = schema_check.get("hash")
            if actual_hash is not None:
                pack_info["actual_schema_hash"] = actual_hash
            if schema_check["status"] == "canonical" and actual_hash is not None and pinned_hash is not None and actual_hash != pinned_hash:
                mismatches.append(
                    f"{entry.name} schema hash {actual_hash} does not match "
                    f"pinned {pinned_hash}"
                )
                pack_info["schema_mismatch"] = True
            elif schema_check["status"] not in {"canonical", "unverified_legacy"}:
                mismatches.append(f"{entry.name} schema evidence is {schema_check['status']}: {schema_check.get('reason', 'unverified')}")

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
    if isinstance(raw, str) and _is_known_pin(raw):
        pinned_commit = raw
    # ReadyMetadata carries the same provenance under ``comfy_core``.  Use it
    # only as a fallback: an explicit workflow-level comfy_commit is the
    # authoritative override.  Unknown/unavailable capture markers are not
    # pins and must not create a false mismatch.
    if pinned_commit is None:
        core = metadata.get("comfy_core")
        if isinstance(core, dict):
            core_commit = core.get("commit")
            if isinstance(core_commit, str) and _is_known_pin(core_commit):
                pinned_commit = core_commit
    pinned["comfy_commit"] = pinned_commit

    installed_commit = _comfyui_git_head()
    actual["comfy_commit"] = installed_commit

    if pinned_commit is not None and installed_commit is not None:
        if pinned_commit != installed_commit:
            mismatches.append(
                f"ComfyUI commit {installed_commit} does not match "
                f"pinned {pinned_commit}"
            )


def _is_known_pin(value: str) -> bool:
    """Return whether a metadata value is an actual commit pin."""
    return bool(value.strip() and value.strip().lower() not in {"unknown", "unavailable", "none", "null"})


# ---------------------------------------------------------------------------
# Filesystem / git helpers (reuse doctor.py patterns)
# ---------------------------------------------------------------------------


def _nodepack_dir(name: str) -> Path | None:
    """Find the on-disk directory for a custom node pack, if installed.

    Searches the configured local-library custom_nodes path first when SET,
    then falls back through the standard locations.
    """
    from vibecomfy.local_library import Slot, resolved_path

    configured = resolved_path(Slot.custom_nodes)
    candidates: list[Path] = []
    if configured is not None:
        candidates.append(configured / name)
    candidates.extend(
        [
        Path("vendor") / name,
        Path("custom_nodes") / name,
        ]
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


def _git_origin(pack_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "remote", "get-url", "origin"],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _comfyui_git_head() -> str | None:
    """Return the git HEAD SHA of the installed ComfyUI, or ``None``."""
    candidates = (Path("ComfyUI"),)
    for candidate in candidates:
        if (candidate / ".git").is_dir():
            return _git_head(candidate)
    return None


def _canonical_pack_schema_hash(entry: Any) -> dict[str, Any]:
    """Return a canonical object_info schema hash when cache metadata supports it."""
    from vibecomfy.porting.object_info import get_class_by_identity

    class_set = tuple(getattr(entry, "class_set", ()) or ())
    pack_slug = getattr(entry, "slug", None) or getattr(entry, "name", None)
    git_commit = getattr(entry, "git_commit_sha", None) or getattr(entry, "commit", None)
    if not class_set:
        return {
            "status": "unverified_legacy",
            "hash": None,
            "reason": "lockfile entry has no class_set for canonical object_info verification",
        }
    if not pack_slug or not git_commit:
        return {
            "status": "unavailable",
            "hash": None,
            "reason": "lockfile entry has no pack slug or git commit identity",
        }

    schemas: dict[str, dict[str, Any]] = {}
    for class_type in class_set:
        cached = get_class_by_identity(class_type, pack_slug=pack_slug, git_commit=git_commit)
        if cached is None:
            return {
                "status": "unavailable",
                "hash": None,
                "reason": f"object_info cache has no canonical entry for {class_type}",
            }
        class_hash = cached.get("class_schema_sha256") or cached.get("schema_hash")
        if not class_hash:
            return {
                "status": "unavailable",
                "hash": None,
                "reason": f"object_info cache entry for {class_type} has no canonical schema hash",
            }
        schemas[class_type] = cached

    return {"status": "canonical", "hash": compute_schema_hash(schemas)}


# ---------------------------------------------------------------------------
# strict-drift gate — called before queue boundaries
# ---------------------------------------------------------------------------


def enforce_strict_drift(
    workflow: VibeWorkflow, *, lockfile_path: str | Path | None = None
) -> None:
    """Collect drift and raise :class:`DriftError` if any mismatches exist.

    This is the pre-queue gate wired into all session paths when
    ``SessionConfig.strict_drift`` is ``True``.
    """
    effective_lockfile_path = lockfile_path
    if effective_lockfile_path is None and not _has_custom_node_requirements(workflow):
        effective_lockfile_path = Path.cwd() / ".vibecomfy-no-lockfile"
    drift = collect_drift(workflow, lockfile_path=effective_lockfile_path)
    mismatches: list[str] = drift.get("mismatches", [])
    if mismatches:
        raise DriftError(
            "Pre-queue drift check failed:\n  - "
            + "\n  - ".join(mismatches),
            next_action="vibecomfy runtime doctor",
        )
