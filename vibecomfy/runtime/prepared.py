"""Dependency preparation for the managed, repeatable workflow runner.

This module is deliberately a composition layer.  Model downloads, node-pack
installation, and canonical workflow loading keep their existing authorities;
the prepared runner only gives them one ordered, inspectable lifecycle.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.model_assets import extract_from_raw_workflow


class PreparationError(RuntimeError):
    """A dependency could not be planned or realized before queueing."""


@dataclass(frozen=True, slots=True)
class PreparationPlan:
    workflow: str
    models: tuple[dict[str, Any], ...] = ()
    custom_nodes: tuple[str, ...] = ()
    python_packages: tuple[str, ...] = ()
    actions: tuple[dict[str, Any], ...] = ()
    declaration_source: str = "workflow metadata"

    def to_json(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "declaration_source": self.declaration_source,
            "models": [dict(entry) for entry in self.models],
            "custom_nodes": list(self.custom_nodes),
            "python_packages": list(self.python_packages),
            "actions": [dict(action) for action in self.actions],
        }


@dataclass(frozen=True, slots=True)
class PreparationResult:
    plan: PreparationPlan
    dry_run: bool
    prepared: bool
    model_paths: tuple[str, ...] = ()
    node_results: tuple[dict[str, Any], ...] = ()
    package_results: tuple[dict[str, Any], ...] = ()
    receipt_path: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": True,
            "dry_run": self.dry_run,
            "prepared": self.prepared,
            "plan": self.plan.to_json(),
            "model_paths": list(self.model_paths),
            "node_results": [dict(result) for result in self.node_results],
            "package_results": [dict(result) for result in self.package_results],
            "receipt_path": self.receipt_path,
            "diagnostics": dict(self.diagnostics),
        }


def _literal_assignments(path: Path) -> dict[str, Any]:
    """Read only literal module assignments; never imports or executes code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise PreparationError(f"could not read preparation declaration {path}: {exc}") from exc
    values: dict[str, Any] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if not node.value or not targets:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in {"PREPARE", "READY_REQUIREMENTS"}:
                try:
                    values[target.id] = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    # READY_METADATA is commonly a constructor call.  It is
                    # intentionally not executed by this reader.
                    continue
    return values


def read_declaration(reference: str | Path) -> dict[str, Any]:
    """Return safe, pre-import dependency declarations when available."""
    path = Path(reference)
    if path.is_file() and path.suffix.lower() == ".py":
        values = _literal_assignments(path)
        declaration = values.get("PREPARE")
        if declaration is None:
            declaration = values.get("READY_REQUIREMENTS", {})
        return dict(declaration) if isinstance(declaration, Mapping) else {}
    if path.is_file() and path.suffix.lower() == ".json":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PreparationError(f"could not read workflow declaration {path}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise PreparationError("workflow declaration must be a JSON object")
        return {"models": extract_from_raw_workflow(raw)}
    return {}


def _normalise_names(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple, set)):
        raise PreparationError("custom_nodes/python_packages declarations must be arrays")
    return tuple(sorted({str(item) for item in value if str(item).strip()}))


def _model_entries(workflow: Any, declaration: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    from vibecomfy.runtime.session import _model_assets_from_workflow

    entries = declaration.get("models")
    if not isinstance(entries, list):
        if workflow is None:
            return ()
        entries = _model_assets_from_workflow(workflow)
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_entry in entries:
        if not isinstance(raw_entry, Mapping):
            raise PreparationError("model declarations must contain objects")
        entry = _reconcile_model_entry(dict(raw_entry))
        name = str(entry.get("name", entry.get("filename", "")))
        subdir = str(entry.get("subdir", entry.get("directory", "")))
        target = str(entry.get("target_path", f"{subdir}/{name}"))
        identity = (target, json.dumps(entry, sort_keys=True, default=str))
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(entry)
    return tuple(normalized)


def _reconcile_model_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Fill a URL/checksum from the local model registry when it can.

    A workflow may know only a logical model name and target directory.  The
    registry is the authority for turning that name into a downloadable URL;
    this function never invents a source.  Unresolved entries remain intact so
    an existing local file can still be reused, while a missing file fails at
    the fetch boundary with its concrete declaration error.
    """
    if isinstance(entry.get("url"), str) and entry["url"]:
        return entry
    name = entry.get("name", entry.get("filename"))
    if not isinstance(name, str) or not name:
        return entry
    subdir = entry.get("subdir", entry.get("directory", ""))
    if not isinstance(subdir, str):
        return entry
    try:
        from vibecomfy.registry.models_loader import load_registry, resolve_model_entry

        registry_entry = resolve_model_entry(
            str(entry.get("model_id", entry.get("id", name))),
            registry=load_registry(),
            subdir=subdir or None,
        )
    except Exception:
        return entry
    if registry_entry is None:
        return entry
    source = registry_entry.source
    url = source.url
    if not url and source.kind == "huggingface" and source.repo and source.filename:
        revision = source.revision or "main"
        url = f"https://huggingface.co/{source.repo}/resolve/{revision}/{source.filename}"
    if not url:
        return entry
    reconciled = dict(entry)
    reconciled["url"] = url
    if not reconciled.get("sha256") and registry_entry.sha256:
        reconciled["sha256"] = registry_entry.sha256
    if reconciled.get("size_bytes") is None and registry_entry.size_bytes is not None:
        reconciled["size_bytes"] = registry_entry.size_bytes
    if not reconciled.get("hf_revision") and source.revision:
        reconciled["hf_revision"] = source.revision
    if registry_entry.gated and "gated" not in reconciled:
        reconciled["gated"] = True
    return reconciled


def build_plan(
    workflow: Any,
    *,
    reference: str | Path,
    declaration: Mapping[str, Any] | None = None,
    ensure_models: bool = True,
    ensure_packs: bool = True,
) -> PreparationPlan:
    declared = dict(declaration or {})
    models = _model_entries(workflow, declared)
    requirements = getattr(workflow, "requirements", None)
    custom_nodes = _normalise_names(
        declared.get("custom_nodes", getattr(requirements, "custom_nodes", ()))
    )
    packages = _normalise_names(declared.get("python_packages"))
    actions: list[dict[str, Any]] = []
    if ensure_packs and custom_nodes:
        actions.append({"kind": "custom_nodes", "status": "planned", "count": len(custom_nodes)})
    if ensure_models and models:
        actions.append({"kind": "models", "status": "planned", "count": len(models)})
    if packages:
        actions.append({"kind": "python_packages", "status": "declared", "count": len(packages)})
    return PreparationPlan(
        workflow=str(reference),
        models=models,
        custom_nodes=custom_nodes,
        python_packages=packages,
        actions=tuple(actions),
        declaration_source="PREPARE/READY_REQUIREMENTS" if declared else "workflow metadata",
    )


def prepare_workflow(
    workflow: Any,
    *,
    reference: str | Path,
    runtime_root: str | Path | None,
    declaration: Mapping[str, Any] | None = None,
    ensure_models: bool = True,
    ensure_packs: bool = True,
    dry_run: bool = False,
    session_id: str | None = None,
    download_workers: int | None = None,
    quiet: bool = False,
) -> PreparationResult:
    """Prepare once per runtime root, serializing setup across callers."""
    if dry_run:
        return _prepare_workflow_unlocked(
            workflow,
            reference=reference,
            runtime_root=runtime_root,
            declaration=declaration,
            ensure_models=ensure_models,
            ensure_packs=ensure_packs,
            dry_run=True,
            session_id=session_id,
            download_workers=download_workers,
            quiet=quiet,
        )
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
            declaration=declaration,
            ensure_models=ensure_models,
            ensure_packs=ensure_packs,
            dry_run=False,
            session_id=session_id,
            download_workers=download_workers,
            quiet=quiet,
        )


def _prepare_workflow_unlocked(
    workflow: Any,
    *,
    reference: str | Path,
    runtime_root: str | Path | None,
    declaration: Mapping[str, Any] | None = None,
    ensure_models: bool = True,
    ensure_packs: bool = True,
    dry_run: bool = False,
    session_id: str | None = None,
    download_workers: int | None = None,
    quiet: bool = False,
) -> PreparationResult:
    """Prepare declared dependencies and persist one receipt before queueing."""
    root = (
        Path(runtime_root).expanduser().resolve(strict=False)
        if runtime_root is not None
        else Path.cwd().resolve(strict=False)
    )
    from vibecomfy import fetch as fetch_assets

    model_root = root / "ComfyUI" / "models" if runtime_root is not None else fetch_assets.models_root()
    plan = build_plan(
        workflow,
        reference=reference,
        declaration=declaration,
        ensure_models=ensure_models,
        ensure_packs=ensure_packs,
    )
    _validate_model_destinations(plan.models, model_root)
    if dry_run:
        return PreparationResult(plan=plan, dry_run=True, prepared=False)

    model_paths: list[str] = []
    model_future: Future[list[Path]] | None = None
    model_executor: ThreadPoolExecutor | None = None
    if ensure_models and plan.models:
        if download_workers is None:
            raw_workers = os.environ.get("VIBECOMFY_PREPARE_DOWNLOAD_WORKERS", "2")
            try:
                download_workers = int(raw_workers)
            except ValueError as exc:
                raise PreparationError(
                    "VIBECOMFY_PREPARE_DOWNLOAD_WORKERS must be a positive integer"
                ) from exc
        if isinstance(download_workers, bool) or download_workers < 1:
            raise PreparationError("download_workers must be a positive integer")
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
        package_results: list[dict[str, Any]] = []
        if plan.python_packages:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", *plan.python_packages],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except (OSError, subprocess.CalledProcessError) as exc:
                detail = getattr(exc, "stderr", None) or str(exc)
                raise PreparationError(f"Python package preparation failed: {detail}") from exc
            package_results = [
                {"name": package, "status": "installed", "interpreter": sys.executable}
                for package in plan.python_packages
            ]

        node_results: list[dict[str, Any]] = []
        if ensure_packs:
            from vibecomfy.node_packs import (
                install_required_packs,
                missing_packs_for_workflow,
                read_lockfile,
            )
            lockfile_path = root / "custom_nodes.lock"

            try:
                try:
                    packs, unresolved = missing_packs_for_workflow(
                        workflow, lockfile_path=lockfile_path
                    )
                except TypeError as exc:
                    if "lockfile_path" not in str(exc):
                        raise
                    packs, unresolved = missing_packs_for_workflow(workflow)
            except Exception as exc:
                raise PreparationError(f"custom-node planning failed: {exc}") from exc
            if unresolved:
                raise PreparationError(
                    "custom-node planning could not resolve class types: " + ", ".join(sorted(unresolved))
                )
            if packs:
                try:
                    restore_entries = read_lockfile(lockfile_path)
                except Exception as exc:
                    raise PreparationError(
                        f"custom-node lockfile could not be read: {exc}"
                    ) from exc
                batch = install_required_packs(
                    packs,
                    install_root=root / "custom_nodes",
                    lockfile_path=lockfile_path,
                    restore_entries=restore_entries,
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
        dry_run=False,
        prepared=True,
        model_paths=tuple(model_paths),
        node_results=tuple(node_results),
        receipt_path=str(receipt_path),
        package_results=tuple(package_results),
        diagnostics={
            "runtime_root": str(root),
            "session_id": session_id,
            "python_executable": sys.executable,
        },
    )
    receipt_path.write_text(json.dumps(result.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _validate_model_destinations(
    entries: tuple[dict[str, Any], ...], root: Path
) -> None:
    """Reject ambiguous declarations before any download can partially run."""
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


def prepare_declared_custom_nodes(
    declaration: Mapping[str, Any], *, runtime_root: str | Path, dry_run: bool = False
) -> tuple[dict[str, Any], ...]:
    """Realize literal pack declarations when a workflow import needs them.

    This is the recovery path for canonical Python bundles whose builder
    imports a node wrapper that is not installed yet.  It is intentionally
    limited to catalogued packs; arbitrary repository URLs belong in a future
    signed declaration extension.
    """
    names = _normalise_names(declaration.get("custom_nodes"))
    if not names or dry_run:
        return ()
    from vibecomfy.node_packs import get_known_node_packs, install_required_packs

    root = Path(runtime_root).expanduser().resolve(strict=False)
    lockfile_path = root / "custom_nodes.lock"
    by_name = {
        pack.name: pack
        for pack in get_known_node_packs(lockfile_path=lockfile_path)
    }
    missing = [name for name in names if name not in by_name]
    if missing:
        raise PreparationError(
            "declared custom-node packs are not in the local catalog: " + ", ".join(missing)
        )
    batch = install_required_packs(
        [by_name[name] for name in names],
        install_root=root / "custom_nodes",
        lockfile_path=root / "custom_nodes.lock",
    )
    results = tuple(
        {
            "name": result.name,
            "status": result.status,
            "git_commit_sha": result.git_commit_sha,
            "error": result.error,
        }
        for result in batch.results
    )
    if not batch.ok:
        details = "; ".join(
            f"{item['name']}: {item['error'] or item['status']}" for item in results
        )
        raise PreparationError(f"declared custom-node preparation failed: {details}")
    return results


__all__ = [
    "PreparationError",
    "PreparationPlan",
    "PreparationResult",
    "build_plan",
    "prepare_workflow",
    "prepare_declared_custom_nodes",
    "read_declaration",
]
