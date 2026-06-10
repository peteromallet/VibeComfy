"""Loader and CLI helpers for ready-template emission."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

from vibecomfy.utils import find_repo_root

REPO_ROOT = find_repo_root()


def load_module_from_path(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"_vibecomfy_inspect_{path.stem}", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_workflow_for(
    template_path: Path,
) -> tuple[Any, dict, dict, str, dict[str, tuple[str, str]] | None]:
    """Drive the parser end and return (workflow, metadata, requirements, id, registered_inputs)."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
    from vibecomfy.registry.ready_template import build_authored_ready_workflow

    module = load_module_from_path(template_path)
    template_id = getattr(module, "READY_METADATA", {}).get("ready_template") or template_path.stem

    if hasattr(module, "API_WORKFLOW"):
        api = dict(module.API_WORKFLOW)
        wf = convert_to_vibe_format(api, source_path=str(template_path), workflow_id=template_id)
        return (
            wf,
            dict(module.READY_METADATA),
            dict(module.READY_REQUIREMENTS),
            template_id,
            None,
        )

    if hasattr(module, "NODES"):
        nodes_tuple = module.NODES
        metadata = dict(module.READY_METADATA)
        # Detect if any class_type is a UUID -- needs subgraph inlining.
        has_uuid = any(re.fullmatch(r"[0-9a-f-]{36}", str(c)) for _, c, _ in nodes_tuple)
        if has_uuid:
            source_path = REPO_ROOT / metadata["source_workflow"]
            ui = json.loads(source_path.read_text())
            api = normalize_to_api(ui, use_comfy_converter=False)
            wf = convert_to_vibe_format(api, source_path=str(template_path), workflow_id=template_id)
        else:
            # No UUID -- just rebuild via authored path; this gives us a working
            # VibeWorkflow with original IDs preserved.
            registered_inputs = extract_registered_inputs(template_path)
            wf = build_authored_ready_workflow(
                nodes_tuple,
                metadata,
                source_path=str(template_path),
                workflow_id=template_id,
                requirements=module.READY_REQUIREMENTS,
                registered_inputs=registered_inputs,
            )
            return (
                wf,
                metadata,
                dict(module.READY_REQUIREMENTS),
                template_id,
                registered_inputs,
            )

        registered_inputs = extract_registered_inputs(template_path)
        return (
            wf,
            metadata,
            dict(module.READY_REQUIREMENTS),
            template_id,
            registered_inputs,
        )

    if hasattr(module, "build"):
        wf = module.build()
        return (
            wf,
            dict(module.READY_METADATA),
            dict(module.READY_REQUIREMENTS),
            template_id,
            extract_registered_inputs(template_path),
        )

    raise RuntimeError(f"Module {template_path} has neither API_WORKFLOW nor NODES")


def extract_registered_inputs(path: Path) -> dict[str, tuple[str, str]] | None:
    text = path.read_text()
    m = re.search(r"registered_inputs=(\{[^}]*\})", text)
    if not m:
        return None
    try:
        # Safe-ish eval of a small dict literal of strings/tuples.
        import ast
        return ast.literal_eval(m.group(1))
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit converted ready_template Python.")
    parser.add_argument("template_path", type=Path)
    args = parser.parse_args(argv)

    path = args.template_path.resolve()
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 2

    workflow, metadata, requirements, template_id, registered_inputs = build_workflow_for(path)
    from vibecomfy.porting.emitter import format_as_python
    text = format_as_python(
        workflow,
        ready_metadata=metadata,
        ready_requirements=requirements,
        template_id=template_id,
        registered_inputs=registered_inputs,
    )
    sys.stdout.write(text)
    return 0


__all__ = [
    "REPO_ROOT",
    "build_workflow_for",
    "extract_registered_inputs",
    "load_module_from_path",
    "main",
]
