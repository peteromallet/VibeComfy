"""Restricted loader for agent-generated Python scratchpads.

This module is the only path that may mint ``agent_generated`` provenance for
Python code. It deliberately accepts the current generated-template subset and
rejects anything that looks like general-purpose Python before compiling or
executing the source.
"""

from __future__ import annotations

import ast
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibecomfy.errors import WorkflowBuildError
from vibecomfy.security.gate import current_gate_context, requesting_provenance, require_confirmation

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

MAX_AGENT_GENERATED_SOURCE_BYTES = 1_000_000
MAX_AGENT_GENERATED_AST_NODES = 50_000

_LOAD_PHASE = "load_python"

_ALLOWED_IMPORTS: dict[str, frozenset[str] | None] = {
    "__future__": frozenset({"annotations"}),
    "vibecomfy.handles": frozenset({"Handle"}),
    "vibecomfy.templates": frozenset(
        {
            "InputSpec",
            "ModelAsset",
            "ReadyMetadata",
            "finalize",
            "new_workflow",
            "node",
            "ref",
        }
    ),
    "vibecomfy.workflow": frozenset({"VibeWorkflow", "WorkflowSource"}),
    "vibecomfy.patches.ltx_lowvram": frozenset({"apply"}),
    "vibecomfy.patches.requirements": frozenset({"ensure_custom_nodes"}),
    "vibecomfy.patches.resolution": frozenset({"resolution"}),
}
_ALLOWED_IMPORT_PREFIXES = ("vibecomfy.nodes.",)

_FORBIDDEN_MODULE_ROOTS = frozenset(
    {
        "asyncio",
        "builtins",
        "ctypes",
        "ftplib",
        "glob",
        "http",
        "importlib",
        "inspect",
        "multiprocessing",
        "os",
        "pathlib",
        "requests",
        "shutil",
        "socket",
        "ssl",
        "subprocess",
        "sys",
        "tempfile",
        "urllib",
    }
)
_FORBIDDEN_NAMES = frozenset(
    {
        "__builtins__",
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "dir",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)
_FORBIDDEN_CALL_NAMES = _FORBIDDEN_NAMES | frozenset({"input"})
_FORBIDDEN_CALL_ATTRS = frozenset(
    {
        "chmod",
        "chown",
        "delete",
        "download",
        "exec_module",
        "exists",
        "expanduser",
        "glob",
        "iterdir",
        "mkdir",
        "open",
        "read",
        "read_bytes",
        "read_text",
        "remove",
        "rename",
        "replace",
        "request",
        "resolve",
        "rmdir",
        "run",
        "send",
        "spawn",
        "unlink",
        "walk",
        "write",
        "write_bytes",
        "write_text",
    }
)
_FORBIDDEN_NODE_TYPES = (
    ast.AsyncFunctionDef,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Lambda,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.Yield,
    ast.YieldFrom,
)
_ALLOWED_DUNDER_NAMES = frozenset({"__file__", "__name__"})


@dataclass(frozen=True)
class ScanFailure:
    """One pre-execution loader-policy failure."""

    code: str
    message: str
    phase: str = _LOAD_PHASE
    line: int | None = None
    column: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "phase": self.phase,
            "code": self.code,
            "message": self.message,
        }
        if self.line is not None:
            payload["line"] = self.line
        if self.column is not None:
            payload["column"] = self.column
        return payload


@dataclass(frozen=True)
class ScanReport:
    """Result of scanning agent-generated Python before execution."""

    ok: bool
    failures: tuple[ScanFailure, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "failures": [failure.to_dict() for failure in self.failures],
        }


class AgentGeneratedLoadError(WorkflowBuildError):
    """Raised when generated Python fails the pre-execution load gate."""

    def __init__(self, message: str, *, report: ScanReport) -> None:
        self.report = report
        super().__init__(
            message,
            next_action="Regenerate the scratchpad using only the VibeComfy generated-template subset.",
        )

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["report"] = self.report.to_dict()
        return payload


def scan_agent_generated_python(source: str) -> ScanReport:
    """Scan generated Python source without executing it."""

    return scan_python_source_with_policy(
        source,
        phase=_LOAD_PHASE,
        max_source_bytes=MAX_AGENT_GENERATED_SOURCE_BYTES,
        max_ast_nodes=MAX_AGENT_GENERATED_AST_NODES,
        allowed_imports=_ALLOWED_IMPORTS,
        allowed_import_prefixes=_ALLOWED_IMPORT_PREFIXES,
    )


def scan_python_source_with_policy(
    source: str,
    *,
    phase: str,
    max_source_bytes: int,
    max_ast_nodes: int,
    allowed_imports: dict[str, frozenset[str] | None] | None = None,
    allowed_import_prefixes: tuple[str, ...] = (),
) -> ScanReport:
    """Scan Python source with the shared AST safety vocabulary."""

    if not isinstance(source, str):
        return _report(
            ScanFailure(
                code="source_type",
                message=f"source must be str, got {type(source).__name__}",
                phase=phase,
            )
        )
    if len(source.encode("utf-8")) > max_source_bytes:
        return _report(
            ScanFailure(
                code="source_too_large",
                message=(
                    "Python source exceeds "
                    f"{max_source_bytes} bytes"
                ),
                phase=phase,
            )
        )
    try:
        tree = ast.parse(source, filename="<agent_generated>")
    except SyntaxError as exc:
        return _report(
            ScanFailure(
                code="syntax_error",
                message=exc.msg,
                phase=phase,
                line=exc.lineno,
                column=exc.offset,
            )
        )

    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > max_ast_nodes:
        return _report(
            ScanFailure(
                code="source_too_large",
                message=(
                    "Python source AST exceeds "
                    f"{max_ast_nodes} nodes"
                ),
                phase=phase,
            )
        )

    visitor = _PythonPolicy(
        phase=phase,
        allowed_imports=allowed_imports or {},
        allowed_import_prefixes=allowed_import_prefixes,
    )
    visitor.visit(tree)
    failures = tuple(visitor.failures)
    return ScanReport(ok=not failures, failures=failures)


def load_agent_generated_scratchpad(path: str | Path) -> VibeWorkflow:
    """Load an AST-scanned generated Python scratchpad as a ``VibeWorkflow``."""

    from vibecomfy.workflow import VibeWorkflow

    path = Path(path)
    source = path.read_text(encoding="utf-8")
    report = scan_agent_generated_python(source)
    if not report.ok:
        raise AgentGeneratedLoadError(
            f"Agent-generated scratchpad failed {_LOAD_PHASE} scan",
            report=report,
        )

    require_confirmation(
        operation="scratchpad_exec",
        class_type=None,  # type: ignore[arg-type]
        provenance="agent_generated",
        capabilities=frozenset({"code_exec"}),
        details={"path": str(path), "loader": "agent_generated"},
        ctx=current_gate_context(),
    )

    module = types.ModuleType(f"vibecomfy_agent_generated_{path.stem}")
    module.__file__ = str(path)
    module.__package__ = ""
    code = compile(ast.parse(source, filename=str(path)), str(path), "exec")
    token = requesting_provenance.set("agent_generated")
    try:
        exec(code, module.__dict__)
        build = getattr(module, "build", None)
        if build is None:
            raise ValueError(f"Agent-generated scratchpad {path} must define build()")
        workflow = build()
    finally:
        requesting_provenance.reset(token)
    if not isinstance(workflow, VibeWorkflow):
        raise WorkflowBuildError(
            f"Scratchpad build() must return VibeWorkflow, got {type(workflow).__name__}",
            next_action="Update build() so it returns a VibeWorkflow instance, then run the scratchpad again.",
        )
    return workflow


def _report(*failures: ScanFailure) -> ScanReport:
    return ScanReport(ok=False, failures=tuple(failures))


class _PythonPolicy(ast.NodeVisitor):
    def __init__(
        self,
        *,
        phase: str,
        allowed_imports: dict[str, frozenset[str] | None],
        allowed_import_prefixes: tuple[str, ...],
    ) -> None:
        self.phase = phase
        self.allowed_imports = allowed_imports
        self.allowed_import_prefixes = allowed_import_prefixes
        self.failures: list[ScanFailure] = []

    def visit(self, node: ast.AST) -> Any:
        if isinstance(node, _FORBIDDEN_NODE_TYPES):
            self._fail(
                node,
                "forbidden_node",
                f"{type(node).__name__} is not allowed in agent-generated scratchpads",
            )
            return None
        return super().visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self._fail(node, "forbidden_import", "plain import statements are not allowed")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if node.level:
            self._fail(node, "forbidden_import", "relative imports are not allowed")
            return
        root = module.split(".", 1)[0]
        if root in _FORBIDDEN_MODULE_ROOTS:
            self._fail(node, "forbidden_import", f"import from {module!r} is not allowed")
            return
        allowed_names = self.allowed_imports.get(module)
        prefix_allowed = any(module.startswith(prefix) for prefix in self.allowed_import_prefixes)
        if allowed_names is None and not prefix_allowed:
            self._fail(node, "forbidden_import", f"import from {module!r} is not allowed")
            return
        for alias in node.names:
            if alias.name == "*":
                self._fail(node, "forbidden_import", "wildcard imports are not allowed")
                continue
            if alias.name.startswith("__") or (alias.asname and alias.asname.startswith("__")):
                self._fail(node, "forbidden_import", "dunder imports are not allowed")
                continue
            if allowed_names is not None and alias.name not in allowed_names:
                self._fail(
                    node,
                    "forbidden_import",
                    f"{alias.name!r} is not allowed from {module!r}",
                )

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            if node.id in _FORBIDDEN_NAMES:
                self._fail(node, "forbidden_name", f"{node.id!r} is not allowed")
            elif node.id.startswith("__") and node.id not in _ALLOWED_DUNDER_NAMES:
                self._fail(node, "dunder_access", f"{node.id!r} is not allowed")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            self._fail(node, "dunder_access", f"dunder attribute {node.attr!r} is not allowed")
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in _FORBIDDEN_CALL_NAMES:
                self._fail(node, "forbidden_call", f"{func.id!r} is not allowed")
            elif func.id in _FORBIDDEN_MODULE_ROOTS:
                self._fail(node, "forbidden_call", f"{func.id!r} is not allowed")
        elif isinstance(func, ast.Attribute):
            if func.attr in _FORBIDDEN_CALL_ATTRS:
                self._fail(node, "forbidden_call", f"method {func.attr!r} is not allowed")
            root = _root_name(func)
            if root in _FORBIDDEN_MODULE_ROOTS:
                self._fail(node, "forbidden_call", f"calls through {root!r} are not allowed")
        self.generic_visit(node)

    def _fail(self, node: ast.AST, code: str, message: str) -> None:
        self.failures.append(
            ScanFailure(
                code=code,
                message=message,
                phase=self.phase,
                line=getattr(node, "lineno", None),
                column=getattr(node, "col_offset", None),
            )
        )


def _root_name(node: ast.AST) -> str | None:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


__all__ = [
    "AgentGeneratedLoadError",
    "ScanFailure",
    "ScanReport",
    "load_agent_generated_scratchpad",
    "scan_agent_generated_python",
    "scan_python_source_with_policy",
]
