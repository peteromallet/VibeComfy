from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibecomfy.errors import WorkflowBuildError
from vibecomfy.security import current_gate_context, require_confirmation
from vibecomfy.security.loader_provenance import _provenance_for_path
from vibecomfy.security.provenance import Provenance

from .workflow import VibeWorkflow

if TYPE_CHECKING:
    # Deferred so importing this module (and hence `vibecomfy.registry.library`,
    # which is on the `vibecomfy` __init__ chain) does not transitively pull
    # in `vibecomfy.runtime.*` via `vibecomfy.schema.provider`.
    from vibecomfy.schema import SchemaProvider  # noqa: F401


def _module_import_context(path: Path) -> tuple[str, Path]:
    """Return an importable module name and temporary sys.path root."""
    package_parts: list[str] = []
    package_dir = path.parent
    while (package_dir / "__init__.py").is_file():
        package_parts.append(package_dir.name)
        package_dir = package_dir.parent
    if package_parts:
        module_name = ".".join((*reversed(package_parts), path.stem))
        return module_name, package_dir
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    return f"vibecomfy_scratchpad_{path.stem}_{digest}", path.parent


def load_scratchpad(
    path: str | Path,
    *,
    provenance_override: Provenance | None = None,
) -> VibeWorkflow:
    path = Path(path).resolve()
    if provenance_override == "agent_generated":
        raise ValueError(
            "agent_generated provenance is reserved for "
            "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad()"
        )
    provenance = provenance_override or _provenance_for_path(path)
    module_name, import_root = _module_import_context(path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not import scratchpad {path}")
    module = importlib.util.module_from_spec(spec)
    prior_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    import_root_str = str(import_root)
    inserted_path = import_root_str not in sys.path
    if inserted_path:
        sys.path.insert(0, import_root_str)
    try:
        require_confirmation(
            operation="scratchpad_exec",
            class_type=None,  # type: ignore[arg-type]
            provenance=provenance,
            capabilities=frozenset({"code_exec"}),
            details={"path": str(path)},
            ctx=current_gate_context(),
        )
        spec.loader.exec_module(module)
        build = getattr(module, "build", None)
        if build is None:
            raise ValueError(f"Scratchpad {path} must define build()")
        workflow = build()
        if not isinstance(workflow, VibeWorkflow):
            raise WorkflowBuildError(
                f"Scratchpad build() must return VibeWorkflow, got {type(workflow).__name__}",
                next_action="Update build() so it returns a VibeWorkflow instance, then run the scratchpad again.",
            )
        return workflow
    finally:
        if inserted_path:
            sys.path.remove(import_root_str)
        if prior_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = prior_module


def render_scratchpad(source: str, *, source_is_path: bool = False, schema_provider: SchemaProvider | None = None) -> str:
    loader = "workflow_from_file" if source_is_path else "workflow_from_id"
    provider_arg = ', schema_provider=get_schema_provider("auto")' if schema_provider is not None else ""
    source_literal = repr(str(source))
    return f'''from vibecomfy import {loader}, run
from vibecomfy.schema import get_schema_provider


def build():
    workflow = {loader}({source_literal}{provider_arg})
    # Edit this file with VibeWorkflow methods, for example:
    # workflow.set_prompt("a cinematic robot painter")
    # workflow.set_seed(123)
    # workflow.set_steps(20)
    return workflow


async def main():
    result = await run(build())
    print(result.outputs)
'''


def render_scratchpad_from_dict(api_workflow: dict[str, Any], *, schema_provider: SchemaProvider | None = None) -> str:
    provider_arg = ', schema_provider=get_schema_provider("auto")' if schema_provider is not None else ""
    return f'''from vibecomfy.ingest import from_api
from vibecomfy.runtime import run
from vibecomfy.schema import get_schema_provider


API_WORKFLOW = {api_workflow!r}


def build():
    workflow = from_api(API_WORKFLOW{provider_arg})
    # Edit this file with VibeWorkflow methods, for example:
    # workflow.set_prompt("a cinematic robot painter")
    # workflow.set_seed(123)
    # workflow.set_steps(20)
    return workflow


async def main():
    result = await run(build())
    print(result.outputs)
'''
