"""Dependency preparation for the local workflow runner.

Model downloads and node-pack installation keep their existing authorities;
this module only gives them one ordered, inspectable lifecycle after canonical
workflow reconciliation has succeeded.
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

class PreparationError(RuntimeError):
    """A dependency could not be planned or realized before queueing."""


@dataclass(frozen=True, slots=True)
class PreparationPlan:
    workflow: str
    models: tuple[dict[str, Any], ...] = ()
    custom_nodes: tuple[str, ...] = ()
    actions: tuple[dict[str, Any], ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "models": [dict(entry) for entry in self.models],
            "custom_nodes": list(self.custom_nodes),
            "actions": [dict(action) for action in self.actions],
        }


@dataclass(frozen=True, slots=True)
class PreparationResult:
    plan: PreparationPlan
    model_paths: tuple[str, ...] = ()
    model_evidence: tuple[dict[str, Any], ...] = ()
    node_results: tuple[dict[str, Any], ...] = ()
    receipt_path: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": True,
            "plan": self.plan.to_json(),
            "model_paths": list(self.model_paths),
            "model_evidence": [dict(entry) for entry in self.model_evidence],
            "node_results": [dict(result) for result in self.node_results],
            "receipt_path": self.receipt_path,
            "diagnostics": dict(self.diagnostics),
        }


def _normalise_names(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple, set)):
        raise PreparationError("custom_nodes must be an array")
    return tuple(sorted({str(item) for item in value if str(item).strip()}))


def _model_entries(workflow: Any) -> tuple[dict[str, Any], ...]:
    if workflow is None:
        return ()
    metadata = getattr(workflow, "metadata", {})
    authored = metadata.get("model_assets") if isinstance(metadata, Mapping) else None
    requirements = getattr(workflow, "requirements", None)
    declared = getattr(requirements, "models", ())
    # Preparation consumes only source-backed rows already present in the
    # canonical IR.  In particular, it must not turn a picker filename into a
    # URL by consulting a model registry.  Metadata is preferred because it is
    # the rich canonical representation; requirements.models is the explicit
    # fallback for older envelopes.
    if isinstance(authored, list) and authored:
        entries = authored
    elif isinstance(declared, (list, tuple)):
        entries = [
            item if isinstance(item, Mapping) else {"name": item}
            for item in declared
            if isinstance(item, (Mapping, str))
        ]
    else:
        entries = []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_entry in entries:
        if not isinstance(raw_entry, Mapping):
            raise PreparationError("model declarations must contain objects")
        entry = dict(raw_entry)
        name = str(entry.get("name", entry.get("filename", "")))
        subdir = str(entry.get("subdir", entry.get("directory", "")))
        target = str(entry.get("target_path", f"{subdir}/{name}"))
        identity = (target, json.dumps(entry, sort_keys=True, default=str))
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(entry)
    return tuple(normalized)


def build_plan(
    workflow: Any,
    *,
    reference: str | Path,
    ensure_models: bool = True,
    ensure_packs: bool = True,
) -> PreparationPlan:
    models = _model_entries(workflow)
    requirements = getattr(workflow, "requirements", None)
    custom_nodes = _normalise_names(getattr(requirements, "custom_nodes", ()))
    actions: list[dict[str, Any]] = []
    if ensure_packs and custom_nodes:
        actions.append({"kind": "custom_nodes", "status": "planned", "count": len(custom_nodes)})
    if ensure_models and models:
        actions.append({"kind": "models", "status": "planned", "count": len(models)})
    return PreparationPlan(
        workflow=str(reference),
        models=models,
        custom_nodes=custom_nodes,
        actions=tuple(actions),
    )


def prepare_workflow(
    workflow: Any,
    *,
    reference: str | Path,
    runtime_root: str | Path | None,
    ensure_models: bool = True,
    ensure_packs: bool = True,
    session_id: str | None = None,
    download_workers: int | None = None,
    quiet: bool = False,
) -> PreparationResult:
    """Prepare once per runtime root, serializing setup across callers."""
    from vibecomfy.runtime.locks import resource_lock

    root = (
        Path(runtime_root).expanduser().resolve(strict=False)
        if runtime_root is not None
        else Path.cwd().resolve(strict=False)
    )
    with resource_lock(root / "out" / "preparations"):
        return _prepare_workflow_unlocked(
            workflow,
            reference=reference,
            runtime_root=runtime_root,
            ensure_models=ensure_models,
            ensure_packs=ensure_packs,
            session_id=session_id,
            download_workers=download_workers,
            quiet=quiet,
        )


def _prepare_workflow_unlocked(
    workflow: Any,
    *,
    reference: str | Path,
    runtime_root: str | Path | None,
    ensure_models: bool = True,
    ensure_packs: bool = True,
    session_id: str | None = None,
    download_workers: int | None = None,
    quiet: bool = False,
) -> PreparationResult:
    """Prepare canonical dependencies and persist one receipt before queueing."""
    root = (
        Path(runtime_root).expanduser().resolve(strict=False)
        if runtime_root is not None
        else Path.cwd().resolve(strict=False)
    )
    from vibecomfy import fetch as fetch_assets

    model_root = root / "ComfyUI" / "models" if runtime_root is not None else fetch_assets.models_root()
    plan = build_plan(workflow, reference=reference, ensure_models=ensure_models, ensure_packs=ensure_packs)
    _validate_model_destinations(plan.models, model_root)
    _validate_model_entries(plan.models)

    lockfile_path = root / "custom_nodes.lock"
    packs: list[Any] = []
    restore_entries: list[Any] = []
    if ensure_packs:
        from vibecomfy.node_packs import (
            build_install_refs_by_name,
            missing_packs_for_workflow,
            preflight_pip_requirements,
            read_lockfile,
            validate_install_refs,
        )

        try:
            restore_entries = read_lockfile(lockfile_path)
            packs, unresolved = missing_packs_for_workflow(
                workflow, lockfile_path=lockfile_path
            )
        except Exception as exc:
            raise PreparationError(f"custom-node planning failed: {exc}") from exc
        if unresolved:
            raise PreparationError(
                "custom-node planning could not resolve class types: "
                + ", ".join(sorted(unresolved))
            )
        try:
            install_refs_by_name = build_install_refs_by_name(workflow, packs)
            ref_error = validate_install_refs(
                packs,
                install_refs_by_name,
                restore_entries,
            )
        except (TypeError, ValueError) as exc:
            raise PreparationError(f"custom-node planning failed: {exc}") from exc
        if ref_error is not None:
            raise PreparationError(ref_error)
        if packs:
            preflight = preflight_pip_requirements(packs)
            if not preflight.ok:
                raise PreparationError(
                    "custom-node dependency preflight failed: "
                    + (preflight.error or "pip preflight failed")
                )

    if download_workers is None:
        raw_workers = os.environ.get("VIBECOMFY_DOWNLOAD_WORKERS", "2")
        try:
            download_workers = int(raw_workers)
        except ValueError as exc:
            raise PreparationError(
                "VIBECOMFY_DOWNLOAD_WORKERS must be a positive integer"
            ) from exc
    if isinstance(download_workers, bool) or download_workers < 1:
        raise PreparationError("download_workers must be a positive integer")

    model_paths: list[str] = []
    model_evidence: list[dict[str, Any]] = []
    model_future: Future[list[Path]] | None = None
    model_executor: ThreadPoolExecutor | None = None
    if ensure_models and plan.models:
        from vibecomfy import fetch as fetch_assets

        model_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vibecomfy-prepare")

        def download_models() -> list[Path]:
            try:
                return fetch_assets.download_many(
                    list(plan.models),
                    root=model_root,
                    max_workers=download_workers,
                    quiet=quiet,
                )
            except TypeError as exc:
                # Keep small embedders that provide the pre-existing fetch
                # seam compatible while the optional concurrency parameter
                # rolls out.
                if "max_workers" not in str(exc):
                    raise
                return fetch_assets.download_many(list(plan.models), root=model_root)

        model_future = model_executor.submit(download_models)

    try:
        node_results: list[dict[str, Any]] = []
        if packs:
            from vibecomfy.node_packs import (
                install_required_packs,
            )
            batch = install_required_packs(
                packs,
                install_root=root / "custom_nodes",
                lockfile_path=lockfile_path,
                restore_entries=restore_entries,
                install_refs_by_name=install_refs_by_name,
            )
            node_results = [
                {
                    "name": result.name,
                    "status": result.status,
                    "git_commit_sha": result.git_commit_sha,
                    "error": result.error,
                }
                for result in batch.results
            ]
            if not batch.ok:
                details = "; ".join(
                    f"{item['name']}: {item['error'] or item['status']}" for item in node_results
                )
                raise PreparationError(f"custom-node preparation failed: {details}")
        if model_future is not None:
            try:
                model_paths = [str(path) for path in model_future.result()]
                for entry in plan.models:
                    receipt = fetch_assets.read_resolution_receipt(entry, root=model_root)
                    if receipt is not None:
                        model_evidence.append(receipt)
            except Exception as exc:
                raise PreparationError(f"model preparation failed: {exc}") from exc
    finally:
        if model_executor is not None:
            model_executor.shutdown(wait=True)

    receipt_dir = root / "out" / "preparations"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    suffix = session_id or "one-shot"
    receipt_path = receipt_dir / f"{Path(str(reference)).stem}-{suffix}.json"
    result = PreparationResult(
        plan=plan,
        model_paths=tuple(model_paths),
        model_evidence=tuple(model_evidence),
        node_results=tuple(node_results),
        receipt_path=str(receipt_path),
        diagnostics={
            "runtime_root": str(root),
            "session_id": session_id,
            "python_executable": sys.executable,
        },
    )
    receipt_path.write_text(json.dumps(result.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _validate_model_entries(entries: tuple[dict[str, Any], ...]) -> None:
    from vibecomfy import fetch as fetch_assets

    missing = [
        str(entry.get("name", entry.get("filename", "<unnamed>")))
        for entry in entries
        if not isinstance(entry.get("url"), str) or not entry["url"].strip()
    ]
    if missing:
        raise PreparationError(
            "model planning could not resolve URLs: " + ", ".join(sorted(set(missing)))
        )
    for entry in entries:
        revision = entry.get("hf_revision") or entry.get("revision")
        if revision is None or revision == "":
            continue
        name = str(entry.get("name", entry.get("filename", "<unnamed>")))
        try:
            fetch_assets._effective_fetch_url(str(entry["url"]), revision)
        except (TypeError, ValueError) as exc:
            raise PreparationError(f"model {name} has an unsupported revision selector: {exc}") from exc


def _validate_model_destinations(
    entries: tuple[dict[str, Any], ...], root: Path
) -> None:
    """Reject ambiguous metadata before any download can partially run."""
    from vibecomfy import fetch as fetch_assets

    seen: dict[Path, tuple[Any, ...]] = {}
    for entry in entries:
        try:
            destination = fetch_assets.local_path(entry, root=root)
        except Exception as exc:
            raise PreparationError(f"invalid model declaration: {exc}") from exc
        identity = (
            entry.get("url"),
            entry.get("sha256"),
            entry.get("hf_revision"),
            entry.get("size_bytes"),
            entry.get("gated"),
        )
        previous = seen.get(destination)
        if previous is not None and previous != identity:
            raise PreparationError(
                f"model destination collision at {destination}; declarations disagree"
            )
        seen[destination] = identity


__all__ = [
    "PreparationError",
    "PreparationPlan",
    "PreparationResult",
    "build_plan",
    "prepare_workflow",
]
