"""Workflow-local custom-node pack registrations and reconciliation helpers.

The global ``custom_nodes.lock`` remains the installed-environment lockfile.
This module only records the missing-class -> pack evidence an agent has
researched for a workflow, in the same spirit as the model sidecar used by
``models register``.  It deliberately does not install anything itself.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml

from vibecomfy.node_packs import CustomNodePack
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import get_schema_provider


SIDECAR_KEY = "node_packs"


def load_final_workflow(workflow_ref: str):
    """Load the same final workflow that node preflight receives."""

    return load_workflow_reference(
        workflow_ref,
        schema_provider=get_schema_provider("auto"),
        allow_scratchpad=True,
    )


def sidecar_path_for_workflow(workflow_ref: str, *, workflow: Any | None = None) -> Path:
    """Return the adjacent ``.nodes.yaml`` path for a file-backed workflow."""

    loaded = workflow if workflow is not None else load_final_workflow(workflow_ref)
    source_path = getattr(getattr(loaded, "source", None), "path", None)
    if not source_path:
        raise ValueError(
            "nodes register requires a file-backed workflow so its local sidecar can be stored"
        )
    return Path(source_path).with_suffix(".nodes.yaml")


def registered_node_packs_for_workflow(
    workflow_ref: str,
    *,
    workflow: Any | None = None,
) -> list[dict[str, Any]]:
    """Read and normalize workflow-local pack registrations.

    A workflow loaded from an in-memory/template source simply has no local
    sidecar.  Registration itself still fails closed for that source because
    there would be nowhere durable to write the mapping.
    """

    try:
        sidecar = sidecar_path_for_workflow(workflow_ref, workflow=workflow)
    except ValueError:
        return []
    if not sidecar.exists():
        return []
    try:
        loaded = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid node sidecar {sidecar}: {exc}") from exc
    if not isinstance(loaded, dict) or not isinstance(loaded.get(SIDECAR_KEY, []), list):
        raise ValueError(f"invalid node sidecar {sidecar}: expected {SIDECAR_KEY}: []")

    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(loaded[SIDECAR_KEY], start=1):
        try:
            rows.append(_normalize_row(raw, index=index))
        except ValueError as exc:
            raise ValueError(f"invalid node sidecar {sidecar}: {exc}") from exc
    _check_duplicate_claims(rows)
    return rows


def registered_packs_for_classes(
    workflow_ref: str,
    class_types: set[str],
    *,
    workflow: Any | None = None,
) -> tuple[list[CustomNodePack], dict[str, dict[str, Any]], set[str]]:
    """Resolve sidecar rows that cover *class_types*.

    Returns concrete pack definitions, install refs keyed by pack name, and
    the class types covered by those rows.  The caller merges these packs with
    the catalog-derived plan and removes covered unresolved classes.
    """

    rows = registered_node_packs_for_workflow(workflow_ref, workflow=workflow)
    packs: list[CustomNodePack] = []
    refs: dict[str, dict[str, Any]] = {}
    covered: set[str] = set()
    by_name: dict[str, CustomNodePack] = {}
    for row in rows:
        matched = class_types & set(row["classes"])
        if not matched:
            continue
        name = str(row["name"])
        repo = str(row["repo"])
        prior = by_name.get(name)
        pack = CustomNodePack(
            name=name,
            repo=repo,
            classes=frozenset(row["classes"]),
            pip_packages=tuple(row.get("pip_packages", ())),
        )
        if prior is not None:
            if prior.repo != pack.repo:
                raise ValueError(
                    f"node sidecar maps pack {name!r} to conflicting repositories"
                )
            pack = CustomNodePack(
                name=name,
                repo=repo,
                classes=prior.classes | pack.classes,
                pip_packages=tuple(sorted(set(prior.pip_packages) | set(pack.pip_packages))),
            )
        by_name[name] = pack
        refs[name] = _install_ref(row)
        covered.update(matched)
    packs = sorted(by_name.values(), key=lambda item: item.name.lower())
    return packs, refs, covered


def merge_registered_packs(
    workflow_ref: str,
    workflow: Any,
    packs: list[CustomNodePack],
    unresolved: list[str],
) -> tuple[list[CustomNodePack], list[str], dict[str, dict[str, Any]]]:
    """Merge sidecar-backed packs into a catalog-derived install plan."""

    registered, install_refs, covered = registered_packs_for_classes(
        workflow_ref,
        set(unresolved),
        workflow=workflow,
    )
    by_name = {pack.name: pack for pack in packs}
    for pack in registered:
        existing = by_name.get(pack.name)
        if existing is not None:
            if existing.repo != pack.repo:
                raise ValueError(
                    f"node sidecar maps pack {pack.name!r} to a different repository"
                )
            by_name[pack.name] = CustomNodePack(
                name=pack.name,
                repo=pack.repo,
                classes=existing.classes | pack.classes,
                pip_packages=tuple(sorted(set(existing.pip_packages) | set(pack.pip_packages))),
            )
        else:
            by_name[pack.name] = pack
    remaining = sorted(set(unresolved) - covered)
    return sorted(by_name.values(), key=lambda item: item.name.lower()), remaining, install_refs


def register_workflow_node(
    workflow_ref: str,
    class_type: str,
    *,
    repo: str,
    name: str | None = None,
    commit: str | None = None,
    version: str | None = None,
) -> int:
    """Record one researched class-to-pack mapping beside a workflow."""

    class_type = class_type.strip()
    repo = repo.strip()
    if not class_type:
        raise ValueError("node class type must not be empty")
    if not repo:
        raise ValueError("--repo must not be empty")
    pack_name = (name or _pack_name_from_repo(repo)).strip()
    if not pack_name:
        raise ValueError("could not infer a pack name from --repo; pass --name")

    sidecar = sidecar_path_for_workflow(workflow_ref)
    rows = registered_node_packs_for_workflow(workflow_ref)
    target: dict[str, Any] | None = None
    for row in rows:
        if class_type in row["classes"]:
            if row["name"] != pack_name or row["repo"] != repo:
                raise ValueError(
                    f"{class_type!r} is already registered to {row['name']!r}; "
                    "use the same pack or edit the sidecar explicitly"
                )
            target = row
            break
        if row["name"] == pack_name and row["repo"] != repo:
            raise ValueError(
                f"pack {pack_name!r} is already registered to a different repository"
            )
    if target is None:
        target = {
            "id": _entry_id(pack_name),
            "name": pack_name,
            "repo": repo,
            "source": {"kind": "git", "url": repo},
            "classes": [],
            "pip_packages": [],
        }
        rows.append(target)
    target["classes"] = sorted(set(target["classes"]) | {class_type})
    if commit is not None:
        target["commit"] = commit
    if version is not None:
        target["version"] = version
    rows.sort(key=lambda row: str(row["name"]).lower())
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        yaml.safe_dump({SIDECAR_KEY: rows}, sort_keys=False),
        encoding="utf-8",
    )
    print(f"registered {class_type} -> {sidecar}")
    return 0


def _normalize_row(raw: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"entry {index} must be a mapping")
    source = raw.get("source")
    source_map = source if isinstance(source, Mapping) else {}
    kind = str(source_map.get("kind") or raw.get("source_kind") or "git")
    if kind != "git":
        raise ValueError(f"entry {index} has unsupported source kind {kind!r}; only git is supported")
    repo = raw.get("repo") or raw.get("url") or source_map.get("url")
    if not isinstance(repo, str) or not repo.strip():
        raise ValueError(f"entry {index} requires repo or source.url")
    name = raw.get("name") or raw.get("slug") or _pack_name_from_repo(repo)
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"entry {index} requires name")
    classes = raw.get("classes") or raw.get("class_types")
    if not isinstance(classes, list) or not classes or any(
        not isinstance(item, str) or not item.strip() for item in classes
    ):
        raise ValueError(f"entry {index} requires a non-empty classes list")
    pip_packages = raw.get("pip_packages") or []
    if not isinstance(pip_packages, list) or any(
        not isinstance(item, str) or not item.strip() for item in pip_packages
    ):
        raise ValueError(f"entry {index} pip_packages must be a list of strings")
    normalized: dict[str, Any] = {
        "id": str(raw.get("id") or _entry_id(str(name))),
        "name": str(name).strip(),
        "repo": repo.strip(),
        "source": {"kind": "git", "url": repo.strip()},
        "classes": sorted({item.strip() for item in classes}),
        "pip_packages": sorted({item.strip() for item in pip_packages}),
    }
    for key in ("commit", "version"):
        value = raw.get(key)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"entry {index} {key} must be a non-empty string")
            normalized[key] = value.strip()
    return normalized


def _check_duplicate_claims(rows: list[dict[str, Any]]) -> None:
    claims: dict[str, str] = {}
    for row in rows:
        for class_type in row["classes"]:
            prior = claims.get(class_type)
            if prior is not None and prior != row["name"]:
                raise ValueError(
                    f"class {class_type!r} is registered to both {prior!r} and {row['name']!r}"
                )
            claims[class_type] = row["name"]


def _install_ref(row: Mapping[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "slug": str(row["name"]),
        "source": "git",
        "url": str(row["repo"]),
    }
    for key in ("commit", "version"):
        if row.get(key) is not None:
            ref[key] = str(row[key])
    return ref


def _entry_id(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", name, flags=re.IGNORECASE).strip("_").lower()
    return f"local_{value or 'node_pack'}"


def _pack_name_from_repo(repo: str) -> str:
    path = (urlparse(repo).path or repo).rstrip("/")
    name = Path(path).name
    return name[:-4] if name.endswith(".git") else name


__all__ = [
    "load_final_workflow",
    "merge_registered_packs",
    "registered_node_packs_for_workflow",
    "registered_packs_for_classes",
    "register_workflow_node",
    "sidecar_path_for_workflow",
]
