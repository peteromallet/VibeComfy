from __future__ import annotations

import ast
import hashlib
import importlib.abc
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

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


@dataclass(frozen=True, slots=True)
class WorkflowDraft:
    """A Python workflow admitted for planning before all evidence is present."""

    workflow: VibeWorkflow
    source_path: Path
    source_revision: str
    unresolved: tuple[dict[str, Any], ...] = ()

    @property
    def ready_for_execution(self) -> bool:
        return not self.unresolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "resolved" if self.ready_for_execution else "unresolved",
            "source_path": str(self.source_path),
            "source_revision": self.source_revision,
            "workflow_id": self.workflow.id,
            "node_count": len(self.workflow.nodes),
            "unresolved": [dict(item) for item in self.unresolved],
        }


def _source_revision(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_spans(path: Path, workflow: VibeWorkflow) -> dict[str, dict[str, int | str]]:
    """Return source locations for constructor calls when they are literal."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return {}
    calls: list[tuple[int, int, str, ast.Call]] = []
    for item in ast.walk(tree):
        if not isinstance(item, ast.Call):
            continue
        func = item.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else ""
        )
        if name not in {"raw_call", "node", "ready_node"} or not item.args:
            continue
        first = item.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            class_type = first.value
        elif (
            name == "raw_call"
            and len(item.args) > 1
            and isinstance(item.args[1], ast.Constant)
            and isinstance(item.args[1].value, str)
        ):
            class_type = item.args[1].value
        else:
            continue
        calls.append((item.lineno, item.col_offset, class_type, item))
    calls.sort(key=lambda row: (row[0], row[1]))
    spans: dict[str, dict[str, int | str]] = {}
    cursor = 0
    for node_id, node in workflow.nodes.items():
        for index in range(cursor, len(calls)):
            line, column, class_type, call = calls[index]
            if class_type != node.class_type:
                continue
            spans[str(node_id)] = {
                "path": str(path),
                "line": int(line),
                "column": int(column),
                "end_line": int(getattr(call, "end_lineno", line)),
                "end_column": int(getattr(call, "end_col_offset", column)),
                "class_type": str(class_type),
            }
            cursor = index + 1
            break
    return spans


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

    def get_code(self, fullname: str) -> Any:
        """Compile the current source bytes instead of trusting a stale pyc.

        Canonical pair publication can replace a source file with another
        same-size revision inside Python's timestamp-granularity window.  A
        normal ``SourceFileLoader`` may then execute the old bytecode while
        the sibling companion already contains the new generation marker.
        The scratchpad boundary is a source-reload boundary, so compile the
        bytes being loaded directly and keep the Python/companion pair bound
        to one revision.
        """
        source = self.actual_path.read_bytes()
        return self.source_to_code(source, str(self.logical_path))



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
    allow_unresolved: bool = False,
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
    # Always use the fresh-source loader, including when the logical and
    # physical paths are identical.  This avoids stale bytecode after an
    # atomic same-basename pair rewrite.
    loader = _MappedSourceLoader(module_name, path, exposed_path)
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
    from vibecomfy.workflow_context import active_workflow

    prior_workflow = active_workflow()
    unresolved_companion_errors: list[str] = []
    try:
        require_confirmation(
            operation="scratchpad_exec",
            class_type=None,  # type: ignore[arg-type]
            provenance=provenance,
            capabilities=frozenset({"code_exec"}),
            details={"path": str(path)},
            ctx=current_gate_context(),
        )
        def execute_build() -> VibeWorkflow:
            spec.loader.exec_module(module)
            build = getattr(module, "build", None)
            if build is None:
                raise ValueError(f"Scratchpad {path} must define build()")
            return build()

        if allow_unresolved:
            from vibecomfy.workflow_bundle import unresolved_companion_context

            with unresolved_companion_context() as errors:
                workflow = execute_build()
                unresolved_companion_errors.extend(errors)
        else:
            workflow = execute_build()
        if not isinstance(workflow, VibeWorkflow):
            raise WorkflowBuildError(
                f"Scratchpad build() must return VibeWorkflow, got {type(workflow).__name__}",
                next_action="Update build() so it returns a VibeWorkflow instance, then run the scratchpad again.",
            )
        if allow_unresolved:
            workflow.metadata["source_revision"] = _source_revision(path)
            workflow.metadata["source_path"] = str(exposed_path)
            spans = _source_spans(exposed_path, workflow)
            if spans:
                workflow.metadata["source_spans"] = spans
            if unresolved_companion_errors:
                existing = workflow.metadata.get("unresolved")
                unresolved = dict(existing) if isinstance(existing, Mapping) else {}
                unresolved["companion"] = list(unresolved_companion_errors)
                workflow.metadata["unresolved"] = unresolved
        return workflow
    finally:
        current_workflow = active_workflow()
        if current_workflow is not None and current_workflow is not prior_workflow:
            token = getattr(current_workflow, "_workflow_context_token", None)
            if token is not None:
                from vibecomfy.workflow_context import reset_workflow

                try:
                    reset_workflow(token)
                finally:
                    current_workflow._workflow_context_token = None
        if finder is not None:
            sys.meta_path.remove(finder)
        if inserted_path:
            sys.path.remove(import_root_str)
        if prior_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = prior_module


def load_scratchpad_draft(
    path: str | Path,
    *,
    provenance_override: Provenance | None = None,
    logical_path: str | Path | None = None,
) -> WorkflowDraft:
    source_path = Path(path).resolve()
    workflow = load_scratchpad(
        source_path,
        provenance_override=provenance_override,
        logical_path=logical_path,
        allow_unresolved=True,
    )
    raw_unresolved = workflow.metadata.get("unresolved")
    unresolved: list[dict[str, Any]] = []
    if isinstance(raw_unresolved, Mapping):
        for kind, values in raw_unresolved.items():
            if isinstance(values, (list, tuple)):
                unresolved.extend(
                    {"kind": str(kind), "message": str(value)} for value in values
                )
            elif values:
                unresolved.append({"kind": str(kind), "message": str(values)})
    return WorkflowDraft(
        workflow=workflow,
        source_path=Path(logical_path).resolve() if logical_path is not None else source_path,
        source_revision=str(
            workflow.metadata.get("source_revision") or _source_revision(source_path)
        ),
        unresolved=tuple(unresolved),
    )


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
