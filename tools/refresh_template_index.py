"""Refresh the checked-in ready-template discovery index.

The index is a lightweight, static artifact for downstream tools that should
not import every ready template just to answer "does this template id exist?".
It is derived from the same runtime discovery path used by
``vibecomfy.registry.ready`` so checked-in metadata cannot drift from the
actual ready-template surface.
"""
from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from vibecomfy.registry.ready import repo_ready_template_ids
from vibecomfy.registry.static_contract import extract_ready_template_contract


# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "template_index.json"
DEFAULT_COVERAGE = REPO_ROOT / "ready_templates/sources" / "manifests" / "coverage.json"
CONTRACT_SHAPE = "workflow_runtime_contract.v1.public_descriptors.v2"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh template_index.json from ready_templates discovery.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if the output file is stale.")
    args = parser.parse_args(argv)

    generated_at = _existing_generated_at(args.output)
    payload = build_template_index(generated_at=generated_at)
    rendered = json.dumps(payload, indent=2, sort_keys=False) + "\n"

    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else None
        if current != rendered:
            print(f"{args.output} is stale; run `python -m tools.refresh_template_index`.", flush=True)
            return 1
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output} ({payload['template_count']} templates)")
    return 0


def build_template_index(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or _existing_generated_at(DEFAULT_OUTPUT)
    coverage = _load_coverage_by_template_id(DEFAULT_COVERAGE)
    templates: list[dict[str, Any]] = []
    for template_id in repo_ready_template_ids():
        path = _ready_template_path(template_id)
        metadata, requirements = _ready_template_metadata(REPO_ROOT / path)
        static_contract = extract_ready_template_contract(REPO_ROOT / path)
        coverage_row = coverage.get(template_id, {})
        coverage_tier = metadata.get("coverage_tier") or coverage_row.get("coverage_tier", "")
        row = {
            "id": template_id,
            "path": path,
            "source_scope": "repo",
            "indexed": True,
            "capability": metadata.get("capability") or coverage_row.get("task", ""),
            "coverage_tier": coverage_tier,
            "custom_nodes": static_contract.get("custom_nodes")
            or sorted(_string_items(requirements.get("custom_nodes"))),
            "model_count": static_contract.get("model_count", len(_list_items(requirements.get("models")))),
            "public_inputs": static_contract["public_inputs"],
            "public_outputs": static_contract["public_outputs"],
            "contract_shape": CONTRACT_SHAPE,
            "artifact_expectations": static_contract["artifact_expectations"],
            "static_diagnostics": static_contract["diagnostics"],
            "public_input_status": _public_status(static_contract["public_inputs"], static_contract["diagnostics"]),
            "public_output_status": _public_status(static_contract["public_outputs"], static_contract["diagnostics"]),
            "custom_node_count": len(
                static_contract.get("custom_nodes")
                or sorted(_string_items(requirements.get("custom_nodes")))
            ),
            "strict_ready_diagnostic_counts": {},
            "readiness_class": static_contract["readiness_class"],
            "marker": static_contract["marker"],
            "app_active": static_contract["app_active"] or coverage_tier == "required",
            "blocked": static_contract["blocked"] or coverage_tier == "blocked",
            "reference": static_contract["reference"] or coverage_tier == "reference",
            "supplemental": static_contract["supplemental"] or coverage_tier == "supplemental",
            "vibecomfy_version": metadata.get("vibecomfy_version"),
            "comfy_core": metadata.get("comfy_core"),
            "source_workflow": (
                (metadata.get("provenance") or {}).get("source_workflow")
                or ("manual" if coverage_row.get("path") == "manual" else None)
            ),
            "source_sha256": _extract_source_sha256(REPO_ROOT / path),
        }
        custom_node_refs = static_contract.get("custom_node_refs") or _list_items(requirements.get("custom_node_refs"))
        if custom_node_refs:
            row["custom_node_refs"] = custom_node_refs
        templates.append(row)

    return {
        "generated_at": generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "generated_from": "repo-only ready template discovery",
        "include_rule": "find ready_templates -type f -name '*.py' ! -name '_*' | sort",
        "exclude_rule": "exclude __init__.py and files whose basename starts with '_' to match vibecomfy.registry.ready._template_paths",
        "template_count": len(templates),
        "templates": templates,
    }


def _ready_template_path(template_id: str) -> str:
    return (Path("ready_templates") / f"{template_id}.py").as_posix()


def _extract_source_sha256(path: Path) -> str | None:
    """Extract source SHA256 from the ``# ported from ... (sha256: ...)`` comment."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    import re
    m = re.search(r"# ported from .+ \(sha256: ([0-9a-f]+)\)", text)
    return m.group(1) if m else None


_KNOWN_TOP_LEVEL_NAMES = frozenset({
    "READY_METADATA",
    "READY_REQUIREMENTS",
    "PUBLIC_INPUTS",
    "MODELS",
    "OUTPUT_PREFIX",
    "PRIVATE_KNOBS",
})


def _ready_template_metadata(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse READY_METADATA and READY_REQUIREMENTS from a template file.

    Handles both literal dict assignments and ``ReadyMetadata.build(...)``
    call expressions.  When requirements are embedded in the
    ``ReadyMetadata.build`` call, they are returned as the second tuple
    element alongside any separate ``READY_REQUIREMENTS`` assignment.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return {}, {}
    assignments: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in _KNOWN_TOP_LEVEL_NAMES:
                continue
            assignments[target.id] = _literal_value(node.value, assignments)
    metadata = assignments.get("READY_METADATA")
    requirements = assignments.get("READY_REQUIREMENTS")
    if isinstance(metadata, dict):
        from vibecomfy.registry.static_contract import _metadata_with_static_derivations

        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            source = ""
        metadata = _metadata_with_static_derivations(metadata, path, source)

    # If READY_METADATA was built via ReadyMetadata.build(...), extract
    # requirements from within it.
    meta_reqs = None
    if isinstance(metadata, dict) and metadata.get("requirements"):
        meta_reqs = metadata["requirements"]
    if meta_reqs is not None and isinstance(meta_reqs, dict):
        if isinstance(requirements, dict):
            # Merge: standalone READY_REQUIREMENTS wins for explicit keys,
            # but meta_reqs fills in missing keys.
            merged = dict(meta_reqs)
            merged.update(requirements)
            requirements = merged
        else:
            requirements = dict(meta_reqs)

    return (
        metadata if isinstance(metadata, dict) else {},
        requirements if isinstance(requirements, dict) else {},
    )


def _literal_value(node: ast.AST, assignments: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_literal_value(item, assignments) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal_value(item, assignments) for item in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _literal_value(key, assignments): _literal_value(value, assignments)
            for key, value in zip(node.keys, node.values)
            if key is not None
        }
    if isinstance(node, ast.Name):
        return assignments.get(node.id)
    if isinstance(node, ast.Subscript):
        value = _literal_value(node.value, assignments)
        key = _literal_value(node.slice, assignments)
        if isinstance(value, dict):
            return value.get(key)
    if isinstance(node, ast.Call):
        return _evaluate_known_call(node, assignments)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _evaluate_known_call(node: ast.Call, assignments: dict[str, Any]) -> Any:
    """Evaluate known builder calls (ReadyMetadata.build, InputSpec, ModelAsset)."""
    from vibecomfy.registry.static_contract import _evaluate_call

    return _evaluate_call(node, assignments)


def _list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_items(value: Any) -> list[str]:
    return [item for item in _list_items(value) if isinstance(item, str)]


def _public_status(items: list[dict[str, Any]], diagnostics: list[dict[str, Any]]) -> str:
    if any(item.get("severity") == "error" for item in diagnostics):
        return "error"
    if items:
        return "declared"
    if diagnostics:
        return "partial"
    return "missing"


def _existing_generated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = current.get("generated_at") if isinstance(current, dict) else None
    return value if isinstance(value, str) and value else None


def _load_coverage_by_template_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    workflows = data.get("workflows", []) if isinstance(data, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for item in workflows:
        if not isinstance(item, dict):
            continue
        keys: list[str] = []
        workflow_id = item.get("id")
        media = item.get("media")
        ready_template = item.get("ready_template")
        if isinstance(workflow_id, str):
            keys.append(workflow_id)
            if isinstance(media, str):
                keys.append(f"{media}/{workflow_id}")
        if isinstance(ready_template, str):
            keys.append(ready_template)
        for key in keys:
            result[key] = item
    return result


if __name__ == "__main__":
    raise SystemExit(main())
