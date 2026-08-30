from __future__ import annotations

import hashlib
import importlib.abc
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

class _MappedSourceLoader(importlib.abc.SourceLoader):
    """Load copied bytes while exposing the caller's logical source path."""

    def __init__(self, fullname: str, actual_path: Path, logical_path: Path) -> None:
        self.fullname = fullname
        self.actual_path = actual_path
        self.logical_path = logical_path

    def get_filename(self, fullname: str) -> str:
        return str(self.logical_path)

    def get_data(self, path: str) -> bytes:
        return self.actual_path.read_bytes() if Path(path) == self.logical_path else Path(path).read_bytes()



class _MappedSourceFinder(importlib.abc.MetaPathFinder):
    """Map copied package modules to their original logical filenames."""

    def __init__(self, actual_root: Path, logical_root: Path) -> None:
        self.actual_root = actual_root
        self.logical_root = logical_root
        self.package_name = (
            actual_root.name if (actual_root / "__init__.py").is_file() else None
        )

    def find_spec(
        self,
        fullname: str,
        path: list[str] | None = None,
        target: Any | None = None,
    ) -> Any:
        if self.package_name is not None:
            if fullname == self.package_name:
                relative = Path()
            elif fullname.startswith(f"{self.package_name}."):
                relative = Path(*fullname.split(".")[1:])
            else:
                return None
        elif "." not in fullname:
            relative = Path(fullname)
        else:
            return None
        actual = self.actual_root / relative
        logical = self.logical_root / relative
        if actual.with_suffix(".py").is_file():
            actual_file = actual.with_suffix(".py")
            logical_file = logical.with_suffix(".py")
            loader = _MappedSourceLoader(fullname, actual_file, logical_file)
            return importlib.util.spec_from_file_location(fullname, logical_file, loader=loader)
        if (actual / "__init__.py").is_file():
            loader = _MappedSourceLoader(
                fullname,
                actual / "__init__.py",
                logical / "__init__.py",
            )
            return importlib.util.spec_from_file_location(
                fullname,
                logical / "__init__.py",
                loader=loader,
                submodule_search_locations=[str(logical)],
            )
        return None

def _source_root(path: Path) -> Path:
    root = path.parent
    if not (root / "__init__.py").is_file():
        return root
    while (root.parent / "__init__.py").is_file():
        root = root.parent
    return root


def load_scratchpad(
    path: str | Path,
    *,
    provenance_override: Provenance | None = None,
    logical_path: str | Path | None = None,
) -> VibeWorkflow:
    path = Path(path).resolve()
    exposed_path = Path(logical_path).resolve() if logical_path is not None else path
    if provenance_override == "agent_generated":
        raise ValueError(
            "agent_generated provenance is reserved for "
            "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad()"
        )
    provenance = provenance_override or _provenance_for_path(exposed_path)
    module_name, import_root = _module_import_context(path)
    loader = (
        _MappedSourceLoader(module_name, path, exposed_path)
        if exposed_path != path
        else None
    )
    spec = importlib.util.spec_from_file_location(
        module_name,
        exposed_path,
        loader=loader,
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not import scratchpad {path}")
    module = importlib.util.module_from_spec(spec)
    prior_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    import_root_str = str(import_root)
    inserted_path = import_root_str not in sys.path
    if inserted_path:
        sys.path.insert(0, import_root_str)
    finder = (
        _MappedSourceFinder(_source_root(path), _source_root(exposed_path))
        if exposed_path != path
        else None
    )
    if finder is not None:
        sys.meta_path.insert(0, finder)
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
        if finder is not None:
            sys.meta_path.remove(finder)
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
