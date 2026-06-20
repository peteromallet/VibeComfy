"""Attempt bundle builder — written before every queue boundary.

Provides :func:`build_attempt_bundle` which collects the full pre-queue
snapshot (prompt, id map, node lookups, model manifest, lockfile, version
info, drift block) and atomically writes ``attempt.json`` into the run
directory.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from vibecomfy.utils import atomic_write_json
from vibecomfy.workflow import VibeWorkflow

logger = logging.getLogger(__name__)


def _collect_drift_for_bundle(workflow: VibeWorkflow) -> dict[str, Any]:
    """Collect drift data for the attempt bundle (import-on-use to avoid
    circular imports)."""
    from vibecomfy.runtime.drift import collect_drift as _collect

    return _collect(workflow)


def build_attempt_bundle(
    workflow: VibeWorkflow,
    api_dict: dict[str, Any],
    *,
    backend: str,
    config: Any = None,
) -> dict[str, Any]:
    """Collect the pre-queue attempt snapshot.

    Parameters:
        workflow:
            The compiled workflow whose prompt is about to be queued.
        api_dict:
            The compiled API dictionary (``workflow.compile(backend=...)``).
        backend:
            Compilation backend used  (``"api"`` / ``"graphbuilder"``).
        config:
            Optional :class:`~vibecomfy.runtime.session.SessionConfig` for
            model-root resolution (used when computing *actual_sha256*).
    """
    from vibecomfy.comfy_nodes.agent.audit import (
        redact_audit_metadata,
        runtime_intent_metadata_from_api,
    )

    redaction_categories: set[str] = set()

    # --- compiled_prompt ----------------------------------------------------
    compiled_redacted = redact_audit_metadata(dict(api_dict))
    redaction_categories.update(compiled_redacted.categories)
    compiled_prompt: dict[str, Any] = compiled_redacted.value if isinstance(compiled_redacted.value, dict) else {}

    # --- id_map --------------------------------------------------------------
    id_map: dict[str, str] = workflow.id_map()

    # --- full node reverse-lookup map ---------------------------------------
    node_lookups: dict[str, dict[str, Any]] = {}
    for node_id in workflow.nodes:
        redacted_lookup = redact_audit_metadata(workflow.lookup_id(node_id))
        redaction_categories.update(redacted_lookup.categories)
        node_lookups[str(node_id)] = redacted_lookup.value if isinstance(redacted_lookup.value, dict) else {}

    # --- source_workflow metadata -------------------------------------------
    source_redacted = redact_audit_metadata(dict(workflow.metadata) if isinstance(workflow.metadata, dict) else {})
    redaction_categories.update(source_redacted.categories)
    source_workflow: dict[str, Any] = source_redacted.value if isinstance(source_redacted.value, dict) else {}

    # --- runtime-backed intent metadata -------------------------------------
    runtime_intent_nodes = runtime_intent_metadata_from_api(api_dict)
    if runtime_intent_nodes:
        redaction_categories.add("runtime_source")

    # --- model asset manifest -----------------------------------------------
    model_manifest = _build_model_manifest(workflow, config=config)

    # --- lockfile snapshot --------------------------------------------------
    lockfile_snapshot = _read_lockfile_snapshot()

    # --- runtime version ----------------------------------------------------
    try:
        from importlib.metadata import version as _pkg_version

        runtime_version: str | None = _pkg_version("vibecomfy")
    except Exception:
        runtime_version = None

    # --- Comfy commit -------------------------------------------------------
    comfy_commit: str | None = None
    if isinstance(workflow.metadata, dict):
        raw = workflow.metadata.get("comfy_commit")
        if isinstance(raw, str) and raw:
            comfy_commit = raw

    # --- drift block (collected from live filesystem / git state) ----------
    drift: dict[str, Any] = _collect_drift_for_bundle(workflow)

    return {
        "compiled_prompt": compiled_prompt,
        "id_map": id_map,
        "node_lookups": node_lookups,
        "source_workflow": source_workflow,
        "runtime_intent_nodes": runtime_intent_nodes,
        "redactions": sorted(redaction_categories),
        "model_manifest": model_manifest,
        "lockfile_snapshot": lockfile_snapshot,
        "runtime_version": runtime_version,
        "comfy_commit": comfy_commit,
        "drift": drift,
    }


def write_attempt_json(
    run_dir: Path,
    bundle: dict[str, Any],
) -> Path:
    """Atomically write *bundle* to ``<run_dir>/attempt.json``."""
    return atomic_write_json(run_dir / "attempt.json", bundle)


# -- helpers ------------------------------------------------------------------


def _build_model_manifest(
    workflow: VibeWorkflow,
    *,
    config: Any = None,
) -> list[dict[str, Any]]:
    """Build the model manifest with *expected_sha256* and *actual_sha256*.

    Uses :func:`~vibecomfy.model_assets.resolve_referenced_assets` directly
    (not ``_model_assets_from_workflow``, which raises on unresolved assets).
    Missing files record ``actual_sha256: null`` per SD2.
    """
    from vibecomfy.model_assets import resolve_referenced_assets

    try:
        resolved, unresolved = resolve_referenced_assets(workflow)
    except Exception:
        logger.debug("model_assets.resolve_referenced_assets failed; manifest will be empty", exc_info=True)
        resolved, unresolved = [], []

    manifest: list[dict[str, Any]] = []
    for asset in resolved:
        entry: dict[str, Any] = {
            "name": asset.get("name"),
            "subdir": asset.get("subdir"),
            "url": asset.get("url"),
            "expected_sha256": asset.get("sha256"),
            "actual_sha256": _compute_actual_sha256(asset, config=config),
        }
        if asset.get("size_bytes") is not None:
            entry["size_bytes"] = asset["size_bytes"]
        if asset.get("hf_revision"):
            entry["hf_revision"] = asset["hf_revision"]
        for key in ("node_id", "class_type", "field", "value", "reference_type", "downloadable"):
            if key in asset:
                entry[key] = asset[key]
        manifest.append(entry)

    # Also include unresolved entries so the manifest is complete
    for ref in unresolved:
        manifest.append(
            {
                "name": ref.get("value"),
                "subdir": ref.get("subdir"),
                "node_id": ref.get("node_id"),
                "class_type": ref.get("class_type"),
                "field": ref.get("field"),
                "value": ref.get("value"),
                "reference_type": ref.get("reference_type"),
                "downloadable": ref.get("downloadable", False),
                "expected_sha256": None,
                "actual_sha256": None,
                "unresolved": True,
            }
        )

    return manifest


def _compute_actual_sha256(asset: dict[str, Any], *, config: Any = None) -> str | None:
    """Compute the SHA-256 of the file on disk referenced by *asset*.

    Returns ``None`` when the file is missing (SD2).
    """
    name = asset.get("name")
    subdir = asset.get("subdir")
    if not isinstance(name, str) or not isinstance(subdir, str):
        return None

    # Resolve the models root
    from vibecomfy.runtime.model_policy import normalized_models_root

    models_root = Path(normalized_models_root())
    candidate_path = models_root / subdir / name
    if not candidate_path.is_file():
        return None

    try:
        sha = hashlib.sha256()
        with open(candidate_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()
    except OSError:
        return None


def _read_lockfile_snapshot() -> dict[str, Any] | None:
    """Return the parsed ``custom_nodes.lock`` contents, or ``None``."""
    lockfile_path = Path("custom_nodes.lock")
    if not lockfile_path.is_file():
        return None
    try:
        return json.loads(lockfile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.debug("Failed to read lockfile snapshot", exc_info=True)
        return None


def build_shared_fields(
    workflow: VibeWorkflow,
    api_dict: dict[str, Any],
    *,
    config: Any = None,
) -> dict[str, Any]:
    """Extract the fields shared between *attempt.json* and *metadata.json*.

    This is a lightweight subset so ``_run_metadata`` can reuse the same
    derivation without duplicating logic.
    """
    bundle = build_attempt_bundle(workflow, api_dict, backend="api", config=config)
    return {
        "compiled_prompt": bundle["compiled_prompt"],
        "id_map": bundle["id_map"],
        "node_lookups": bundle["node_lookups"],
        "source_workflow": bundle["source_workflow"],
        "runtime_intent_nodes": bundle["runtime_intent_nodes"],
        "redactions": bundle["redactions"],
        "model_manifest": bundle["model_manifest"],
        "lockfile_snapshot": bundle["lockfile_snapshot"],
        "runtime_version": bundle["runtime_version"],
        "comfy_commit": bundle["comfy_commit"],
        "drift": bundle["drift"],
    }
