"""Authoritative scenario-manifest generation and validation.

The live lane is descriptor-addressed: the manifest fixes both the selected
scenario set and every scenario/source-workflow byte stream before model calls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIOS_DIR = Path(__file__).with_name("scenarios")
DEFAULT_MANIFEST_PATH = Path(__file__).with_name("scenario_manifest.json")
DESCRIPTOR_SUFFIXES = {".json", ".yaml", ".yml"}


class ScenarioManifestError(ValueError):
    """Raised when the selected live-agentic corpus differs from its manifest."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path_for(scenarios_dir: Path) -> Path:
    if scenarios_dir.resolve() == DEFAULT_SCENARIOS_DIR.resolve():
        return DEFAULT_MANIFEST_PATH
    return scenarios_dir.parent / "scenario_manifest.json"


def _repo_relative(path: Path, *, repo: Path) -> str:
    try:
        # Keep the checkout-relative symlink spelling (not the symlink target),
        # because external_workflows/ is intentionally mounted into worktrees.
        return path.absolute().relative_to(repo.absolute()).as_posix()
    except ValueError as exc:
        raise ScenarioManifestError(f"manifest path escapes repository root: {path}") from exc


def _effective_repo(scenarios_dir: Path, repo: Path) -> Path:
    """Use the real repo for lane data and a temp parent for isolated tests."""
    try:
        scenarios_dir.absolute().relative_to(repo.absolute())
    except ValueError:
        return scenarios_dir.parent
    return repo


def build_manifest(
    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
    *,
    repo: Path = REPO,
    revised_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic manifest for descriptor files already on disk."""
    repo = _effective_repo(scenarios_dir, repo)
    revised_ids = revised_ids or set()
    entries: list[dict[str, Any]] = []
    for path in sorted(
        item for item in scenarios_dir.iterdir() if item.suffix in DESCRIPTOR_SUFFIXES
    ):
        if path.suffix != ".json":
            raise ScenarioManifestError(f"authoritative scenarios must be JSON: {path}")
        scenario = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(scenario, Mapping):
            raise ScenarioManifestError(f"scenario descriptor must contain an object: {path}")
        scenario_id = str(scenario.get("id") or "")
        if not scenario_id or scenario_id != path.stem:
            raise ScenarioManifestError(
                f"scenario id/stem mismatch: id={scenario_id!r}, path={path}"
            )
        workflow_path = scenario.get("workflow_path")
        source_workflow: dict[str, str] | None = None
        if workflow_path:
            source_path = Path(str(workflow_path))
            if not source_path.is_absolute():
                source_path = repo / source_path
            if not source_path.is_file():
                raise ScenarioManifestError(
                    f"scenario {scenario_id!r} workflow_path does not resolve: {workflow_path}"
                )
            source_id = str((scenario.get("_tags") or {}).get("source_workflow_id") or source_path.stem)
            source_workflow = {
                "id": source_id,
                "path": _repo_relative(source_path, repo=repo),
                "sha256": sha256_file(source_path),
            }
        scenario_kind = "edit"
        if (scenario.get("classification") or {}).get("kind") == "health_control":
            scenario_kind = "health_control"
        elif scenario.get("answer_rubric"):
            scenario_kind = "semantic_product"
        entries.append(
            {
                "id": scenario_id,
                "path": _repo_relative(path, repo=repo),
                "descriptor_sha256": sha256_file(path),
                "inclusion_status": "included",
                "revision_status": "revised" if scenario_id in revised_ids else "matched",
                "scenario_kind": scenario_kind,
                "source_workflow": source_workflow,
            }
        )
    return {
        "schema_version": 1,
        "scenario_root": _repo_relative(scenarios_dir, repo=repo),
        "scenario_count": len(entries),
        "entries": entries,
    }


def write_manifest(
    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
    *,
    manifest_path: Path | None = None,
    repo: Path = REPO,
    revised_ids: set[str] | None = None,
) -> Path:
    """Write a deterministic manifest. Used by corpus maintenance and tests."""
    target = manifest_path or manifest_path_for(scenarios_dir)
    payload = build_manifest(scenarios_dir, repo=repo, revised_ids=revised_ids)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def discover_manifest_scenarios(
    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
    *,
    manifest_path: Path | None = None,
    repo: Path = REPO,
) -> list[Path]:
    """Validate the complete manifest contract and return included paths in order."""
    repo = _effective_repo(scenarios_dir, repo)
    manifest_path = manifest_path or manifest_path_for(scenarios_dir)
    if not manifest_path.is_file():
        raise ScenarioManifestError(f"scenario manifest is missing: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioManifestError(f"scenario manifest is unreadable: {exc}") from exc
    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != 1:
        raise ScenarioManifestError("scenario manifest schema_version must be 1")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ScenarioManifestError("scenario manifest entries must be a list")

    expected_root = _repo_relative(scenarios_dir, repo=repo)
    if manifest.get("scenario_root") != expected_root:
        raise ScenarioManifestError(
            f"scenario_root mismatch: expected {expected_root!r}, got {manifest.get('scenario_root')!r}"
        )

    selected: list[Path] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ScenarioManifestError(f"manifest entry {index} must be an object")
        inclusion_status = entry.get("inclusion_status")
        if inclusion_status not in {"included", "excluded"}:
            raise ScenarioManifestError(
                f"manifest entry {index} has invalid inclusion_status: {inclusion_status!r}"
            )
        scenario_id = str(entry.get("id") or "")
        rel_path = str(entry.get("path") or "")
        if not scenario_id or scenario_id in seen_ids:
            raise ScenarioManifestError(f"missing or duplicate scenario id: {scenario_id!r}")
        if not rel_path or rel_path in seen_paths:
            raise ScenarioManifestError(f"missing or duplicate scenario path: {rel_path!r}")
        seen_ids.add(scenario_id)
        seen_paths.add(rel_path)
        path = repo / rel_path
        try:
            path.resolve().relative_to(scenarios_dir.resolve())
        except ValueError as exc:
            raise ScenarioManifestError(f"scenario path is outside scenario_root: {rel_path}") from exc
        if not path.is_file():
            raise ScenarioManifestError(f"manifested scenario is missing: {rel_path}")
        if path.stem != scenario_id:
            raise ScenarioManifestError(
                f"manifest id/path-stem mismatch: id={scenario_id!r}, path={rel_path!r}"
            )
        actual_descriptor_hash = sha256_file(path)
        if actual_descriptor_hash != entry.get("descriptor_sha256"):
            raise ScenarioManifestError(
                f"scenario descriptor hash mismatch for {scenario_id}: "
                f"expected {entry.get('descriptor_sha256')}, got {actual_descriptor_hash}"
            )
        try:
            scenario = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScenarioManifestError(
                f"scenario descriptor is unreadable for {scenario_id}: {exc}"
            ) from exc
        if not isinstance(scenario, Mapping):
            raise ScenarioManifestError(
                f"scenario descriptor must contain an object for {scenario_id}"
            )
        if scenario.get("id") != scenario_id:
            raise ScenarioManifestError(
                f"descriptor id mismatch for {scenario_id}: got {scenario.get('id')!r}"
            )
        workflow_path = scenario.get("workflow_path")
        source = entry.get("source_workflow")
        if workflow_path:
            if not isinstance(source, Mapping):
                raise ScenarioManifestError(f"source workflow metadata missing for {scenario_id}")
            source_path = repo / str(source.get("path") or "")
            expected_source_path = Path(str(workflow_path))
            if not expected_source_path.is_absolute():
                expected_source_path = repo / expected_source_path
            if source_path.resolve() != expected_source_path.resolve():
                raise ScenarioManifestError(f"source workflow path mismatch for {scenario_id}")
            if not source_path.is_file():
                raise ScenarioManifestError(f"source workflow is missing for {scenario_id}: {source_path}")
            expected_source_id = str(
                (scenario.get("_tags") or {}).get("source_workflow_id") or source_path.stem
            )
            if source.get("id") != expected_source_id:
                raise ScenarioManifestError(f"source workflow id mismatch for {scenario_id}")
            actual_source_hash = sha256_file(source_path)
            if actual_source_hash != source.get("sha256"):
                raise ScenarioManifestError(
                    f"source workflow hash mismatch for {scenario_id}: "
                    f"expected {source.get('sha256')}, got {actual_source_hash}"
                )
        elif source is not None:
            raise ScenarioManifestError(f"unexpected source workflow metadata for {scenario_id}")
        if inclusion_status == "included":
            selected.append(path)

    declared_count = manifest.get("scenario_count")
    if declared_count != len(selected):
        raise ScenarioManifestError(
            f"scenario_count mismatch: expected {declared_count}, selected {len(selected)}"
        )
    discovered = {
        _repo_relative(path, repo=repo)
        for path in scenarios_dir.iterdir()
        if path.suffix in DESCRIPTOR_SUFFIXES
    }
    unmanifested = sorted(discovered - seen_paths)
    if unmanifested:
        raise ScenarioManifestError(
            "unmanifested scenario descriptor(s): " + ", ".join(unmanifested)
        )
    missing_from_directory = sorted(seen_paths - discovered)
    if missing_from_directory:
        raise ScenarioManifestError(
            "manifested scenario descriptor(s) missing from directory: "
            + ", ".join(missing_from_directory)
        )
    return selected
