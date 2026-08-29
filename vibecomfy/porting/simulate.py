"""In-memory rule simulation for codemod experiments.

Provides :func:`simulate_rule` which applies text transforms to ready-template
sources in memory, validates canonical parity via ``port_convert_workflow()``,
and computes LOC deltas without modifying any files or ``emitter.py``.
"""

from __future__ import annotations

import difflib
import re
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
    # For boolean rules, apply only when value is truthy
    if rule_value.lower() in ("true", "1", "yes", "on"):
        return transform(source)
    return source


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
        stage = "transformed source load"
        try:
            with tempfile.TemporaryDirectory(prefix="vibecomfy-port-simulate-") as tmp:
                transformed_path = Path(tmp) / tpl_path.name
                transformed_path.write_text(transformed, encoding="utf-8")
                transformed_loaded = load_port_source(
                    str(transformed_path),
                    schema_provider=schema_provider,
                )

            stage = "transformed source compile"
            transformed_api = transformed_loaded.workflow.compile("api")

            stage = "transformed conversion"
            conv_result = port_convert_workflow(
                transformed_loaded.workflow,
                source_path=str(tpl_path),
                source_hash=transformed_loaded.source_hash,
                schema_provider=schema_provider,
                validate=True,
            )
            validation = conv_result.validation
            conversion_parity_ok = bool(
                validation is not None
                and validation.ok
                and validation.parity_ok is True
                and validation.parity_error is None
            )
            entry["conversion_parity_ok"] = conversion_parity_ok

            stage = "original baseline load"
            original_loaded = load_port_source(
                str(tpl_path),
                schema_provider=schema_provider,
            )
            stage = "original baseline compile"
            original_api = original_loaded.workflow.compile("api")
            semantic_parity_ok, semantic_diffs = compile_equivalent(
                original_api,
                transformed_api,
            )
            entry["semantic_parity_ok"] = semantic_parity_ok

            parity_diffs = list(semantic_diffs)
            if validation is not None:
                parity_diffs.extend(
                    f"conversion: {diff}" for diff in validation.parity_diffs
                )
            if parity_diffs:
                entry["parity_diffs"] = parity_diffs

            entry["parity_ok"] = semantic_parity_ok and conversion_parity_ok
            errors: list[str] = []
            if not semantic_parity_ok:
                errors.append("transformed workflow diverged from original")
            if not conversion_parity_ok:
                detail = None
                if validation is not None:
                    detail = validation.parity_error or validation.error
                errors.append(
                    "transformed conversion parity failed"
                    + (f": {detail}" if detail else "")
                )
            if errors:
                entry["error"] = "; ".join(errors)
        except Exception as exc:
            entry["parity_ok"] = False
            entry["error"] = f"{stage} failed: {type(exc).__name__}: {exc}"

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


__all__ = [
    "SimulationPerTemplate",
    "SimulationResult",
    "simulate_rule",
]
