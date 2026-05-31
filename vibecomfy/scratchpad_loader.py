from __future__ import annotations

import importlib.util
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


def load_scratchpad(
    path: str | Path,
    *,
    provenance_override: Provenance | None = None,
) -> VibeWorkflow:
    path = Path(path)
    if provenance_override == "agent_generated":
        raise ValueError(
            "agent_generated provenance is reserved for "
            "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad()"
        )
    provenance = provenance_override or _provenance_for_path(path)
    spec = importlib.util.spec_from_file_location(f"vibecomfy_scratchpad_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not import scratchpad {path}")
    module = importlib.util.module_from_spec(spec)
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
    return f'''from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.runtime import run
from vibecomfy.schema import get_schema_provider


API_WORKFLOW = {api_workflow!r}


def build():
    workflow = convert_to_vibe_format(API_WORKFLOW{provider_arg})
    # Edit this file with VibeWorkflow methods, for example:
    # workflow.set_prompt("a cinematic robot painter")
    # workflow.set_seed(123)
    # workflow.set_steps(20)
    return workflow


async def main():
    result = await run(build())
    print(result.outputs)
'''
