"""Isolated rule simulation for codemod experiments.

Provides :func:`simulate_rule` which applies text transforms to ready-template
sources in memory, validates canonical parity via ``port_convert_workflow()``,
and computes LOC deltas without modifying any caller files or ``emitter.py``.
"""

from __future__ import annotations

import contextlib
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.parity import compile_equivalent
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.schema import get_schema_provider
from vibecomfy.utils import find_repo_root

_REPO_ROOT = find_repo_root()


@dataclass
class SimulationPerTemplate:
    """Result for one template in a simulation."""

    template_id: str
    path: str
    original_loc: int
    emitted_loc: int
    loc_delta: int
    parity_ok: bool
    error: str | None = None


@dataclass
class SimulationResult:
    """Aggregate simulation result."""

    rule_spec: str
    templates_total: int
    templates_affected: int
    loc_delta_total: int
    parity_preserved: int
    parity_broken: int
    per_template: list[dict[str, Any]] = field(default_factory=list)
    sample_diff: str = ""
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "rule_spec": self.rule_spec,
            "templates_total": self.templates_total,
            "templates_affected": self.templates_affected,
            "loc_delta_total": self.loc_delta_total,
            "parity_preserved": self.parity_preserved,
            "parity_broken": self.parity_broken,
            "per_template": self.per_template,
            "sample_diff": self.sample_diff,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Rule transforms — each returns the transformed text
# ---------------------------------------------------------------------------


def _apply_drop_set_id_map(source: str) -> str:
    """Strip all _set_id_map(...) lines."""
    lines = source.splitlines(keepends=True)
    result = [line for line in lines if not re.search(r"_set_id_map\s*\(", line)]
    return "".join(result)


# Registry of known rule transforms
_TRANSFORMS: dict[str, Any] = {
    "drop_set_id_map": _apply_drop_set_id_map,
}


def _parse_rule_spec(rule_spec: str) -> tuple[str, str]:
    """Parse a ``name=value`` rule spec into (name, value)."""
    if "=" in rule_spec:
        name, value = rule_spec.split("=", 1)
        return name.strip(), value.strip().strip('"').strip("'")
    return rule_spec.strip(), "true"


def _apply_rule(source: str, rule_name: str, rule_value: str) -> str:
    """Apply a named rule transform to *source*."""
    transform = _TRANSFORMS.get(rule_name)
    if transform is None:
        return source
    normalized = rule_value.lower()
    if normalized not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise ValueError(
            f"Invalid boolean value for {rule_name!r}: {rule_value!r}; "
            "expected true/false, 1/0, yes/no, or on/off"
        )
    if normalized in {"true", "1", "yes", "on"}:
        return transform(source)
    return source


class _ArtifactExecutionError(RuntimeError):
    """A transformed artifact failed in the isolated worker."""

    def __init__(self, stage: str, detail: str) -> None:
        super().__init__(detail)
        self.stage = stage


def _artifact_source_root(path: Path) -> Path:
    """Return the smallest tree that preserves the source package context."""
    root = path.parent
    if not (root / "__init__.py").is_file():
        return root
    while (root.parent / "__init__.py").is_file():
        root = root.parent
    return root


def _materialize_transformed_source(
    source_path: Path,
    transformed: str,
    destination: Path,
) -> Path:
    """Copy source context into *destination* and replace only the target file."""
    source_path = source_path.resolve()
    source_root = _artifact_source_root(source_path)
    copied_root = destination / source_root.name
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source_root,
        copied_root,
        ignore=shutil.ignore_patterns("__pycache__", ".git"),
    )
    transformed_path = copied_root / source_path.relative_to(source_root)
    transformed_path.write_text(transformed, encoding="utf-8")
    return transformed_path


def _worker_environment() -> dict[str, str]:
    env = dict(os.environ)
    repo_root = str(_REPO_ROOT)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = repo_root if not existing else repo_root + os.pathsep + existing
    env["PYTHONHASHSEED"] = "0"
    return env


def _run_artifact_worker(
    path: Path,
    *,
    schema_mode: str,
    convert: bool,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "vibecomfy.porting.simulate",
        "--_artifact-worker",
        str(path),
        "--schema-mode",
        schema_mode,
    ]
    if convert:
        command.append("--convert")
    try:
        completed = subprocess.run(
            command,
            cwd=_artifact_source_root(path).parent,
            env=_worker_environment(),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _ArtifactExecutionError(
            "isolated artifact worker",
            f"{type(exc).__name__}: {exc}",
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise _ArtifactExecutionError(
            "isolated artifact worker",
            f"worker exited {completed.returncode}: {detail}",
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise _ArtifactExecutionError(
            "isolated artifact worker",
            f"invalid worker response: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise _ArtifactExecutionError(
            "isolated artifact worker",
            "invalid worker response: expected object",
        )
    if payload.get("ok") is not True:
        raise _ArtifactExecutionError(
            str(payload.get("stage") or "artifact execution"),
            str(payload.get("error") or "worker reported failure"),
        )
    return payload


def _artifact_worker_main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--_artifact-worker", required=True)
    parser.add_argument("--schema-mode", choices=("auto", "none"), default="none")
    parser.add_argument("--convert", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args._artifact_worker).resolve()
    stage = "schema provider"
    try:
        schema_provider = (
            get_schema_provider("auto") if args.schema_mode == "auto" else None
        )
        stage = "artifact load"
        with contextlib.redirect_stdout(io.StringIO()):
            loaded = load_port_source(str(path), schema_provider=schema_provider)
            stage = "artifact compile"
            api = loaded.workflow.compile("api")
            payload: dict[str, Any] = {"ok": True, "api": api}
            if args.convert:
                stage = "transformed conversion"
                conversion = port_convert_workflow(
                    loaded.workflow,
                    source_path=str(path),
                    source_hash=loaded.source_hash,
                    schema_provider=schema_provider,
                    validate=True,
                )
                validation = conversion.validation
                payload["validation"] = validation.to_json() if validation else None
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": stage,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0


def simulate_rule(
    rule_spec: str,
    template_ids: list[str] | None = None,
    *,
    schema_provider: Any = None,
) -> SimulationResult:
    """Simulate applying *rule_spec* corpus-wide.

    Changed templates are loaded from a temporary transformed artifact. Their
    compiled API is compared with the original template API, then the canonical
    conversion path validates that the transformed workflow can be emitted and
    reloaded without further divergence.

    Args:
        rule_spec: ``name=value`` rule specification (e.g. ``drop_set_id_map=true``).
        template_ids: Optional list of template IDs to simulate. If None, runs
            across all regeneratable templates from the corpus.
        schema_provider: Optional schema provider for parity validation.

    Returns:
        A :class:`SimulationResult` with per-template stats, aggregate LOC delta,
        parity counts, and a sample diff.
    """
    rule_name, rule_value = _parse_rule_spec(rule_spec)

    if rule_name not in _TRANSFORMS:
        return SimulationResult(
            rule_spec=rule_spec,
            templates_total=0,
            templates_affected=0,
            loc_delta_total=0,
            parity_preserved=0,
            parity_broken=0,
            error=f"Unknown rule: {rule_name!r}. Available: {sorted(_TRANSFORMS.keys())}",
        )
    try:
        _apply_rule("", rule_name, rule_value)
    except ValueError as exc:
        return SimulationResult(
            rule_spec=rule_spec,
            templates_total=0,
            templates_affected=0,
            loc_delta_total=0,
            parity_preserved=0,
            parity_broken=0,
            error=str(exc),
        )


    if schema_provider is None:
        schema_provider = get_schema_provider("auto")

    snapshot = build_corpus_snapshot(_REPO_ROOT / "ready_templates")
    templates_by_id = {template["id"]: template for template in snapshot.templates_list}
    if template_ids is None:
        target_ids = [
            template["id"]
            for template in snapshot.templates_list
            if template["marker"] == "generated"
        ]
    else:
        target_ids = list(dict.fromkeys(template_ids))

    result = SimulationResult(
        rule_spec=rule_spec,
        templates_total=0,
        templates_affected=0,
        loc_delta_total=0,
        parity_preserved=0,
        parity_broken=0,
    )
    per_template: list[dict[str, Any]] = []
    sample_diff = ""

    for tid in target_ids:
        template = templates_by_id.get(tid)
        if template is None:
            per_template.append(
                {
                    "template_id": tid,
                    "path": "",
                    "original_loc": 0,
                    "emitted_loc": 0,
                    "loc_delta": 0,
                    "parity_ok": False,
                    "semantic_parity_ok": None,
                    "conversion_parity_ok": None,
                    "changed": False,
                    "error": f"template not found in corpus: {tid}",
                }
            )
            continue

        tpl_path = Path(template["path"])
        try:
            original_source = tpl_path.read_text(encoding="utf-8")
        except OSError as exc:
            per_template.append(
                {
                    "template_id": tid,
                    "path": str(tpl_path),
                    "original_loc": 0,
                    "emitted_loc": 0,
                    "loc_delta": 0,
                    "parity_ok": False,
                    "semantic_parity_ok": None,
                    "conversion_parity_ok": None,
                    "changed": False,
                    "error": f"source read failed: {type(exc).__name__}: {exc}",
                }
            )
            continue

        original_loc = len([line for line in original_source.splitlines() if line.strip()])
        transformed = _apply_rule(original_source, rule_name, rule_value)
        emitted_loc = len([line for line in transformed.splitlines() if line.strip()])
        changed = transformed != original_source
        entry: dict[str, Any] = {
            "template_id": tid,
            "path": str(tpl_path),
            "original_loc": original_loc,
            "emitted_loc": emitted_loc,
            "loc_delta": emitted_loc - original_loc,
            "parity_ok": True,
            "semantic_parity_ok": True,
            "conversion_parity_ok": None,
            "changed": changed,
        }

        if not changed:
            per_template.append(entry)
            continue

        if not sample_diff:
            diff_lines = difflib.unified_diff(
                original_source.splitlines(keepends=True),
                transformed.splitlines(keepends=True),
                fromfile=str(tpl_path),
                tofile=f"{tpl_path} (simulated)",
            )
            sample_diff = "".join(diff_lines)

        entry["semantic_parity_ok"] = None
        schema_mode = "auto" if schema_provider is not None else "none"
        artifact_paths: list[Path] = []
        try:
            with tempfile.TemporaryDirectory(
                prefix="vibecomfy-port-simulate-"
            ) as tmp:
                temp_root = Path(tmp)
                transformed_path = _materialize_transformed_source(
                    tpl_path,
                    transformed,
                    temp_root / "transformed",
                )
                original_path = _materialize_transformed_source(
                    tpl_path,
                    original_source,
                    temp_root / "original",
                )
                artifact_paths.extend((transformed_path, original_path))
                transformed_payload = _run_artifact_worker(
                    transformed_path,
                    schema_mode=schema_mode,
                    convert=True,
                )
                transformed_api = transformed_payload["api"]
                original_payload = _run_artifact_worker(
                    original_path,
                    schema_mode=schema_mode,
                    convert=False,
                )
                original_api = original_payload["api"]

            semantic_parity_ok, semantic_diffs = compile_equivalent(
                original_api,
                transformed_api,
            )
            entry["semantic_parity_ok"] = semantic_parity_ok
            validation = transformed_payload.get("validation")
            conversion_parity_ok = bool(
                isinstance(validation, dict)
                and validation.get("ok") is True
                and validation.get("parity_ok") is True
                and validation.get("parity_error") is None
            )
            entry["conversion_parity_ok"] = conversion_parity_ok

            parity_diffs = list(semantic_diffs)
            if isinstance(validation, dict):
                parity_diffs.extend(
                    f"conversion: {diff}"
                    for diff in validation.get("parity_diffs", [])
                )
            if parity_diffs:
                entry["parity_diffs"] = parity_diffs

            entry["parity_ok"] = semantic_parity_ok and conversion_parity_ok
            errors: list[str] = []
            if not semantic_parity_ok:
                errors.append("transformed workflow diverged from original")
            if not conversion_parity_ok:
                detail = None
                if isinstance(validation, dict):
                    detail = validation.get("parity_error") or validation.get("error")
                errors.append(
                    "transformed conversion parity failed"
                    + (f": {detail}" if detail else "")
                )
            if errors:
                entry["error"] = "; ".join(errors)
        except _ArtifactExecutionError as exc:
            detail = str(exc)
            for artifact_path in artifact_paths:
                detail = detail.replace(str(artifact_path), "<artifact>")
            entry["parity_ok"] = False
            entry["error"] = f"{exc.stage} failed: {detail}"
        per_template.append(entry)

    result.per_template = per_template
    result.sample_diff = sample_diff
    result.templates_total = len(per_template)
    result.templates_affected = sum(
        1 for entry in per_template if entry.get("changed") is True
    )
    result.loc_delta_total = sum(
        int(entry.get("loc_delta", 0)) for entry in per_template
    )
    result.parity_preserved = sum(
        1 for entry in per_template if entry.get("parity_ok") is True
    )
    result.parity_broken = result.templates_total - result.parity_preserved
    return result


if __name__ == "__main__":
    if "--_artifact-worker" in sys.argv:
        raise SystemExit(_artifact_worker_main(sys.argv[1:]))

__all__ = [
    "SimulationPerTemplate",
    "SimulationResult",
    "simulate_rule",
]
