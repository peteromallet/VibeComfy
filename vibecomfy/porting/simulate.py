"""Bounded parity simulation for pure generated templates.

Simulation is deliberately not a sandbox for arbitrary Python.  Sources are
admitted by a small AST contract, then each admitted source is executed once in
an isolated subprocess.  The parent owns schema capture and conversion.
"""

from __future__ import annotations

import ast
import difflib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.parity import compile_equivalent
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.schema import (
    capture_schema_snapshot,
    get_schema_provider,
    schema_for,
    schema_payload_from_node_schema,
    schema_snapshot_provider_from_payload,
    schema_snapshot_to_payload,
    schemas_for,
)
from vibecomfy.utils import find_repo_root
from vibecomfy.workflow import VibeWorkflow

_REPO_ROOT = find_repo_root()
_SOURCE_LIMIT = 2 * 1024 * 1024
_PROTOCOL_LIMIT = 64 * 1024
_WORKER_STDOUT_LIMIT = 16 * 1024
_WORKER_STDERR_LIMIT = 16 * 1024
_WORKER_TIMEOUT = 30
_ALLOWED_IMPORTED_NAMES: dict[str, frozenset[str]] = {
    "vibecomfy.templates": frozenset({"InputSpec", "ModelAsset", "ReadyMetadata", "new_workflow", "node"}),
    "vibecomfy.workflow": frozenset({"VibeWorkflow", "WorkflowSource"}),
    "vibecomfy.patches.ltx_lowvram": frozenset({"apply"}),
    "vibecomfy.patches.requirements": frozenset({"ensure_custom_nodes"}),
    "vibecomfy.patches.resolution": frozenset({"resolution"}),
}
_ALLOWED_NODE_MODULES = frozenset(
    {
        "vibecomfy.nodes.controlnet_aux",
        "vibecomfy.nodes.core",
        "vibecomfy.nodes.custom_scripts",
        "vibecomfy.nodes.depthanythingv2",
        "vibecomfy.nodes.florence2",
        "vibecomfy.nodes.gguf",
        "vibecomfy.nodes.gimm_vfi",
        "vibecomfy.nodes.kjnodes",
        "vibecomfy.nodes.ltxvideo",
        "vibecomfy.nodes.melbandroformer",
        "vibecomfy.nodes.qwentts",
        "vibecomfy.nodes.rgthree",
        "vibecomfy.nodes.sam2",
        "vibecomfy.nodes.vibecomfy_internal",
        "vibecomfy.nodes.videohelpersuite",
        "vibecomfy.nodes.wananimatepreprocess",
        "vibecomfy.nodes.wanvideowrapper",
    }
)
_ALLOWED_IMPORT_ALIASES = {
    ("vibecomfy.templates", "node", "raw_call"),
    ("vibecomfy.patches.ltx_lowvram", "apply", "apply_ltx_lowvram"),
}
_DETERMINISTIC_BUILTINS = frozenset(
    {"bool", "float", "int", "len", "max", "min", "range", "str", "tuple"}
)
_FORBIDDEN_CALLS: dict[str, tuple[str, str]] = {
    "open": ("forbidden_source_read", "source/file reads are not admitted"),
    "eval": ("forbidden_dynamic_execution", "eval is not admitted"),
    "exec": ("forbidden_dynamic_execution", "exec is not admitted"),
    "compile": ("forbidden_dynamic_execution", "dynamic compilation is not admitted"),
    "__import__": ("forbidden_dynamic_import", "dynamic imports are not admitted"),
    "getattr": ("forbidden_introspection", "dynamic attribute lookup is not admitted"),
    "setattr": ("forbidden_introspection", "dynamic attribute mutation is not admitted"),
    "delattr": ("forbidden_introspection", "dynamic attribute mutation is not admitted"),
    "hasattr": ("forbidden_introspection", "dynamic attribute inspection is not admitted"),
    "dir": ("forbidden_introspection", "introspection is not admitted"),
    "vars": ("forbidden_introspection", "introspection is not admitted"),
    "globals": ("forbidden_introspection", "introspection is not admitted"),
    "locals": ("forbidden_introspection", "introspection is not admitted"),
    "print": ("forbidden_external_io", "stdout I/O is not admitted"),
    "input": ("forbidden_external_io", "stdin I/O is not admitted"),
}
_FORBIDDEN_IMPORTS: dict[str, tuple[str, str]] = {
    "os": ("forbidden_environment", "OS/environment access is not admitted"),
    "sys": ("forbidden_protocol_fd", "process/protocol access is not admitted"),
    "subprocess": ("forbidden_process", "subprocess execution is not admitted"),
    "socket": ("forbidden_network", "network access is not admitted"),
    "ssl": ("forbidden_network", "network access is not admitted"),
    "sqlite3": ("forbidden_database", "database access is not admitted"),
    "random": ("forbidden_entropy", "uncontrolled entropy is not admitted"),
    "secrets": ("forbidden_entropy", "uncontrolled entropy is not admitted"),
    "uuid": ("forbidden_entropy", "uncontrolled entropy is not admitted"),
    "time": ("forbidden_time", "time/process dependence is not admitted"),
    "datetime": ("forbidden_time", "time/process dependence is not admitted"),
    "pathlib": ("forbidden_source_read", "filesystem access is not admitted"),
}


@dataclass(frozen=True)
class TemplateAdmission:
    """Static admission decision; unsupported is distinct from parity failure."""

    status: Literal["admitted", "unsupported"]
    reason: dict[str, Any] | None = None
    node_classes: tuple[str, ...] = ()

    @property
    def admitted(self) -> bool:
        return self.status == "admitted"

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "node_classes": list(self.node_classes),
        }


class _AdmissionRejected(Exception):
    def __init__(self, code: str, message: str, node: ast.AST | None = None) -> None:
        self.code = code
        self.message = message
        self.node = node


class _BindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = {"__file__"}
        self.imported: dict[str, tuple[str, str]] = {}
        self.future_annotations = False
        self.static_names: set[str] = set()

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        if module == "__future__" and any(alias.name == "annotations" for alias in node.names):
            self.future_annotations = True
        for alias in node.names:
            if alias.name == "*":
                continue
            local = alias.asname or alias.name
            self.names.add(local)
            self.imported[local] = (module, alias.name)
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".")[0])

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            self.names.add(arg.arg)
        if node.args.vararg:
            self.names.add(node.args.vararg.arg)
        if node.args.kwarg:
            self.names.add(node.args.kwarg.arg)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(
            ast.FunctionDef(
                name=node.name,
                args=node.args,
                body=node.body,
                decorator_list=node.decorator_list,
                returns=node.returns,
                type_comment=node.type_comment,
            )
        )

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._collect_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._collect_target(node.target)
        self.generic_visit(node)

    def _collect_target(self, node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            self.names.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                self._collect_target(item)


def _is_allowed_node_constructor(module: str, name: str) -> bool:
    if module not in _ALLOWED_NODE_MODULES:
        return False
    try:
        imported_module = importlib.import_module(module)
    except (ImportError, AttributeError, RuntimeError):
        return False
    constructors = getattr(imported_module, "__vibecomfy_class_types__", {})
    return isinstance(constructors, dict) and name in constructors and callable(getattr(imported_module, name, None))

class _AdmissionVisitor(ast.NodeVisitor):
    _allowed_nodes = (
        ast.Module,
        ast.Expr,
        ast.Import,
        ast.ImportFrom,
        ast.alias,
        ast.FunctionDef,
        ast.arguments,
        ast.arg,
        ast.Assign,
        ast.AnnAssign,
        ast.Return,
        ast.Call,
        ast.keyword,
        ast.Name,
        ast.Attribute,
        ast.Constant,
        ast.Dict,
        ast.List,
        ast.Tuple,
        ast.Subscript,
        ast.Slice,
        ast.UnaryOp,
        ast.UAdd,
        ast.USub,
        ast.Not,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
        ast.If,
        ast.IfExp,
        ast.For,
        ast.JoinedStr,
        ast.FormattedValue,
        ast.Load,
        ast.Store,
    )
    def __init__(self, collector: _BindingCollector) -> None:
        self.collector = collector
        self.node_classes: set[str] = set()
        self._function_depth = 0


    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("__") or node.decorator_list:
            self._reject("unsupported_builder", "decorators and dunder builders are not admitted", node)
        self._function_depth += 1
        try:
            if self.collector.future_annotations:
                for default in (*node.args.defaults, *node.args.kw_defaults):
                    if default is not None:
                        self.visit(default)
                for statement in node.body:
                    self.visit(statement)
            else:
                self.generic_visit(node)
        finally:
            self._function_depth -= 1

    def visit(self, node: ast.AST) -> Any:
        if not isinstance(node, self._allowed_nodes):
            self._reject("unsupported_syntax", f"{type(node).__name__} is not admitted", node)
        return super().visit(node)

    def _reject(self, code: str, message: str, node: ast.AST | None = None) -> None:
        raise _AdmissionRejected(code, message, node)

    def visit_Module(self, node: ast.Module) -> None:
        for statement in node.body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                continue
            self.visit(statement)
        if not any(isinstance(statement, ast.FunctionDef) and statement.name == "build" for statement in node.body):
            self._reject("missing_build", "generated template must define build()", node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module = alias.name
            forbidden = _FORBIDDEN_IMPORTS.get(module)
            if forbidden:
                self._reject(*forbidden, node)
            self._reject("forbidden_import", f"import {module!r} is not an admitted repository construct", node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        if node.level:
            self._reject("forbidden_import", "relative imports are not admitted", node)
        if module == "__future__":
            if any(alias.name != "annotations" or alias.asname for alias in node.names):
                self._reject("forbidden_import", "only future annotations is admitted", node)
            return
        forbidden = _FORBIDDEN_IMPORTS.get(module)
        if forbidden:
            self._reject(*forbidden, node)
        allowed_names = _ALLOWED_IMPORTED_NAMES.get(module)
        is_node_module = module in _ALLOWED_NODE_MODULES
        if allowed_names is None and not is_node_module:
            code = "arbitrary_provider_import" if ("schema" in module or "provider" in module) else "forbidden_import"
            self._reject(code, f"import {module!r} is not an admitted repository construct", node)
        for alias in node.names:
            if alias.name == "*":
                self._reject("forbidden_import", "star imports are not admitted", node)
            allowed = (
                _is_allowed_node_constructor(module, alias.name)
                if is_node_module
                else alias.name in (allowed_names or ())
            )
            if not allowed:
                self._reject(
                    "forbidden_import_name",
                    f"name {alias.name!r} is not in the generated template vocabulary for {module!r}",
                    node,
                )
            if alias.asname and (module, alias.name, alias.asname) not in _ALLOWED_IMPORT_ALIASES:
                self._reject(
                    "forbidden_import_alias",
                    f"alias {alias.asname!r} is not admitted for imported name {alias.name!r}",
                    node,
                )

    def visit_If(self, node: ast.If) -> None:
        if not _deterministic_expr(node.test, self.collector.static_names):
            self._reject("unsupported_control", "if conditions must be deterministic literals", node)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        if not _deterministic_expr(node.iter, self.collector.static_names):
            self._reject("unsupported_control", "for loops require deterministic literal iteration", node)
        length = _literal_length(node.iter)
        if length is None or length > 1024:
            self._reject("unsupported_control", "for loops must have at most 1024 literal items", node)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._reject("unsupported_control", "while loops are not admitted", node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            self._reject("forbidden_introspection", f"private attribute {node.attr!r} is not admitted", node)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id not in self.collector.names and node.id not in _DETERMINISTIC_BUILTINS:
            self._reject("unknown_name", f"name {node.id!r} is not bound by the generated module", node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(not _simple_target(target) for target in node.targets):
            self._reject("unsupported_builder", "only local name assignments are admitted", node)
        if _deterministic_expr(node.value, self.collector.static_names):
            for target in node.targets:
                self.collector.static_names.update(_target_names(target))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not _simple_target(node.target):
            self._reject("unsupported_builder", "only local name assignments are admitted", node)
        if node.value is not None and _deterministic_expr(node.value, self.collector.static_names):
            self.collector.static_names.update(_target_names(node.target))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            forbidden = _FORBIDDEN_CALLS.get(node.func.id)
            if forbidden:
                self._reject(*forbidden, node)
            allowed = node.func.id in _DETERMINISTIC_BUILTINS or node.func.id in self.collector.names
            if not allowed:
                self._reject("unsupported_call", f"call to {node.func.id!r} is not admitted", node)
            imported = self.collector.imported.get(node.func.id)
            if imported and imported[0].startswith("vibecomfy.nodes."):
                self.node_classes.add(imported[1])
            if node.func.id == "raw_call" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                self.node_classes.add(node.args[0].value)
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr.startswith("_"):
                self._reject("forbidden_introspection", f"private call {node.func.attr!r} is not admitted", node)
        else:
            self._reject("unsupported_call", "dynamic callable expressions are not admitted", node)
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return
        if self._function_depth == 0:
            self._reject("unsupported_builder", "top-level execution must be declarations", node)
        self.generic_visit(node)


def _simple_target(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) or (
        isinstance(node, (ast.Tuple, ast.List)) and all(_simple_target(item) for item in node.elts)
    )


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        result: set[str] = set()
        for item in node.elts:
            result.update(_target_names(item))
        return result
    return set()


def _deterministic_expr(node: ast.AST, static_names: set[str]) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (str, int, float, bool, type(None)))
    if isinstance(node, ast.Name):
        return node.id in static_names or node.id in {"True", "False", "None"}
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(_deterministic_expr(item, static_names) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (key is None or _deterministic_expr(key, static_names)) and _deterministic_expr(value, static_names)
            for key, value in zip(node.keys, node.values)
        )
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)) and _deterministic_expr(node.operand, static_names)
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)) and _deterministic_expr(node.left, static_names) and _deterministic_expr(node.right, static_names)
    if isinstance(node, ast.BoolOp):
        return isinstance(node.op, (ast.And, ast.Or)) and all(_deterministic_expr(value, static_names) for value in node.values)
    if isinstance(node, ast.Compare):
        return _deterministic_expr(node.left, static_names) and all(_deterministic_expr(item, static_names) for item in node.comparators)
    if isinstance(node, ast.IfExp):
        return all(_deterministic_expr(item, static_names) for item in (node.test, node.body, node.orelse))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
        return all(_deterministic_expr(arg, static_names) for arg in node.args)
    return False


def _literal_length(node: ast.AST) -> int | None:
    if isinstance(node, (ast.Tuple, ast.List)):
        return len(node.elts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
        values = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, int)]
        if len(values) != len(node.args):
            return None
        return len(range(*values))
    return None


def admit_template_source(source: str) -> TemplateAdmission:
    """Return a deterministic static admission decision without executing source."""
    if not isinstance(source, str):
        return TemplateAdmission("unsupported", {"code": "invalid_source", "message": "source must be text"})
    if len(source.encode("utf-8")) > _SOURCE_LIMIT:
        return TemplateAdmission("unsupported", {"code": "source_too_large", "message": "source exceeds admission limit"})
    if not source.lstrip().startswith("# vibecomfy: generated"):
        return TemplateAdmission("unsupported", {"code": "missing_generated_marker", "message": "only generated templates are admitted"})
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return TemplateAdmission(
            "unsupported",
            {"code": "syntax_error", "message": f"{type(exc).__name__}: {exc.msg}", "line": exc.lineno, "column": exc.offset},
        )
    collector = _BindingCollector()
    collector.visit(tree)
    try:
        _AdmissionVisitor(collector).visit(tree)
    except _AdmissionRejected as exc:
        node = exc.node
        return TemplateAdmission(
            "unsupported",
            {
                "code": exc.code,
                "message": exc.message,
                "line": getattr(node, "lineno", None),
                "column": getattr(node, "col_offset", None),
            },
        )
    visitor = _AdmissionVisitor(collector)
    visitor.visit(tree)
    return TemplateAdmission("admitted", node_classes=tuple(sorted(visitor.node_classes)))


@dataclass
class SimulationPerTemplate:
    template_id: str
    path: str
    original_loc: int
    emitted_loc: int
    loc_delta: int
    parity_ok: bool | None
    error: str | None = None


@dataclass
class SimulationResult:
    rule_spec: str
    templates_total: int
    templates_affected: int
    loc_delta_total: int
    parity_preserved: int
    parity_broken: int
    unsupported: int = 0
    per_template: list[dict[str, Any]] = field(default_factory=list)
    sample_diff: str = ""
    error: str | None = None
    schema_snapshot_digest: str | None = None

    @property
    def status(self) -> str:
        if self.error or self.parity_broken:
            return "failed"
        if self.unsupported:
            return "unsupported"
        return "ok"

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rule_spec": self.rule_spec,
            "templates_total": self.templates_total,
            "templates_affected": self.templates_affected,
            "loc_delta_total": self.loc_delta_total,
            "parity_preserved": self.parity_preserved,
            "parity_broken": self.parity_broken,
            "unsupported": self.unsupported,
            "per_template": self.per_template,
            "sample_diff": self.sample_diff,
            "schema_snapshot_digest": self.schema_snapshot_digest,
            "error": self.error,
        }


def _apply_drop_set_id_map(source: str) -> str:
    lines = source.splitlines(keepends=True)
    return "".join(line for line in lines if not re.search(r"_set_id_map\s*\(", line))


_TRANSFORMS: dict[str, Any] = {"drop_set_id_map": _apply_drop_set_id_map}


def _parse_rule_spec(rule_spec: str) -> tuple[str, str]:
    if "=" not in rule_spec:
        return rule_spec.strip(), "true"
    name, raw_value = rule_spec.split("=", 1)
    value = raw_value.strip()
    if not value:
        return name.strip(), value
    quote = value[0] if value[0] in "\"'" else None
    if quote is not None:
        if len(value) < 2 or value[-1] != quote or any(character in "\"'" for character in value[1:-1]):
            raise ValueError(f"Malformed quoted boolean value for {name.strip()!r}: {raw_value!r}")
        value = value[1:-1]
    elif any(character in "\"'" for character in value):
        raise ValueError(f"Malformed quoted boolean value for {name.strip()!r}: {raw_value!r}")
    return name.strip(), value


def _apply_rule(source: str, rule_name: str, rule_value: str) -> str:
    transform = _TRANSFORMS.get(rule_name)
    if transform is None:
        return source
    normalized = rule_value.lower()
    if normalized not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise ValueError(f"Invalid boolean value for {rule_name!r}: {rule_value!r}; expected true/false, 1/0, yes/no, or on/off")
    return transform(source) if normalized in {"true", "1", "yes", "on"} else source


class _ArtifactExecutionError(RuntimeError):
    def __init__(self, stage: str, detail: str) -> None:
        super().__init__(detail)
        self.stage = stage


def _artifact_source_root(path: Path) -> Path:
    root = path.parent
    if not (root / "__init__.py").is_file():
        return root
    while (root.parent / "__init__.py").is_file():
        root = root.parent
    return root


def _materialize_transformed_source(source_path: Path, transformed: str, destination: Path) -> Path:
    source_path = source_path.resolve()
    source_root = _artifact_source_root(source_path)
    copied_root = destination / source_root.name
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root, copied_root, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    transformed_path = copied_root / source_path.relative_to(source_root)
    transformed_path.write_text(transformed, encoding="utf-8")
    return transformed_path


def _worker_environment() -> dict[str, str]:
    env = dict(os.environ)
    root = str(_REPO_ROOT)
    env["PYTHONPATH"] = root if not env.get("PYTHONPATH") else root + os.pathsep + env["PYTHONPATH"]
    env["PYTHONHASHSEED"] = "0"
    return env


def _run_artifact_worker(path: Path, *, logical_path: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "vibecomfy.porting.simulate",
        "--_artifact-worker",
        str(path),
        "--logical-path",
        str(logical_path),
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=_artifact_source_root(path).parent,
            env=_worker_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
    except OSError as exc:
        raise _ArtifactExecutionError("isolated artifact worker", f"{type(exc).__name__}: {exc}") from exc
    try:
        stdout, stderr = process.communicate(timeout=_WORKER_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate()
        raise _ArtifactExecutionError("isolated artifact worker", f"worker timed out after {_WORKER_TIMEOUT}s") from exc
    if len(stdout) > _PROTOCOL_LIMIT:
        raise _ArtifactExecutionError("protocol", f"worker response exceeded {_PROTOCOL_LIMIT} bytes")
    if process.returncode != 0:
        detail = bytes(stderr[:_WORKER_STDERR_LIMIT]).decode("utf-8", errors="replace").strip()
        if not detail:
            detail = bytes(stdout[:_WORKER_STDOUT_LIMIT]).decode("utf-8", errors="replace").strip()
        raise _ArtifactExecutionError("isolated artifact worker", f"worker exited {process.returncode}: {detail}")
    try:
        payload = json.loads(bytes(stdout).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _ArtifactExecutionError("protocol", f"invalid worker response: {exc}") from exc
    if not isinstance(payload, dict):
        raise _ArtifactExecutionError("protocol", "invalid worker response: expected object")
    if payload.get("ok") is not True:
        raise _ArtifactExecutionError(str(payload.get("stage") or "artifact execution"), str(payload.get("error") or "worker reported failure"))
    if not isinstance(payload.get("api"), dict) or not isinstance(payload.get("envelope"), dict):
        raise _ArtifactExecutionError("protocol", "worker response omitted API or IR envelope")
    return payload


def _emit_worker_payload(payload: dict[str, Any], protocol_fd: int) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > _PROTOCOL_LIMIT:
        encoded = json.dumps({"ok": False, "stage": "protocol", "error": f"worker payload exceeded {_PROTOCOL_LIMIT} bytes"}, separators=(",", ":")).encode("utf-8")
    if protocol_fd < 0:
        sys.stdout.buffer.write(encoded)
        return
    written = 0
    while written < len(encoded):
        written += os.write(protocol_fd, encoded[written:])


def _artifact_execution_main(argv: list[str]) -> int:
    import argparse
    import contextlib
    import io

    parser = argparse.ArgumentParser()
    parser.add_argument("--_artifact-exec", required=True)
    parser.add_argument("--logical-path")
    args = parser.parse_args(argv)
    path = Path(args._artifact_exec).resolve()
    logical_path = Path(args.logical_path).resolve() if args.logical_path else path
    stage = "artifact execution"
    try:
        with contextlib.redirect_stdout(io.StringIO()) as captured_stdout:
            stage = "artifact load"
            loaded = load_port_source(str(path), logical_source_path=str(logical_path), schema_provider=None)
            stage = "artifact compile"
            api = loaded.workflow.compile("api")
            envelope = loaded.workflow.to_envelope()
            stdout = captured_stdout.getvalue()
        _emit_worker_payload(
            {
                "ok": True,
                "api": api,
                "envelope": envelope,
                "stdout": stdout[:_WORKER_STDOUT_LIMIT],
                "stdout_truncated": len(stdout) > _WORKER_STDOUT_LIMIT,
            },
            -1,
        )
        return 0
    except Exception as exc:
        _emit_worker_payload({"ok": False, "stage": stage, "error": f"{type(exc).__name__}: {exc}"}, -1)
        return 0


def _artifact_worker_main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--_artifact-worker", required=True)
    parser.add_argument("--logical-path")
    args = parser.parse_args(argv)
    path = Path(args._artifact_worker).resolve()
    logical_path = Path(args.logical_path).resolve() if args.logical_path else path
    command = [
        sys.executable,
        "-m",
        "vibecomfy.porting.simulate",
        "--_artifact-exec",
        str(path),
        "--logical-path",
        str(logical_path),
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=_artifact_source_root(path).parent,
            env=_worker_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
        stdout, stderr = process.communicate(timeout=_WORKER_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        _emit_worker_payload({"ok": False, "stage": "isolated artifact worker", "error": f"worker timed out after {_WORKER_TIMEOUT}s"}, -1)
        return 0
    except OSError as exc:
        _emit_worker_payload({"ok": False, "stage": "isolated artifact worker", "error": f"{type(exc).__name__}: {exc}"}, -1)
        return 0
    if process.returncode != 0:
        detail = bytes(stderr[:_WORKER_STDERR_LIMIT]).decode("utf-8", errors="replace").strip()
        _emit_worker_payload({"ok": False, "stage": "isolated artifact worker", "error": f"worker exited {process.returncode}: {detail}"}, -1)
        return 0
    if len(stdout) > _PROTOCOL_LIMIT:
        _emit_worker_payload({"ok": False, "stage": "protocol", "error": f"worker response exceeded {_PROTOCOL_LIMIT} bytes"}, -1)
        return 0
    try:
        payload = json.loads(bytes(stdout).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _emit_worker_payload({"ok": False, "stage": "protocol", "error": f"invalid worker response: {exc}"}, -1)
        return 0
    if not isinstance(payload, dict):
        _emit_worker_payload({"ok": False, "stage": "protocol", "error": "invalid worker response: expected object"}, -1)
        return 0
    _emit_worker_payload(payload, -1)
    return 0


def _freeze_schema_snapshot(provider: Any | None, node_classes: set[str]) -> dict[str, Any]:
    raw_schemas: dict[str, Any] = {}
    if provider is not None:
        all_schemas = schemas_for(provider)
        if all_schemas is not None:
            candidates = all_schemas.items()
        else:
            candidates = ((class_type, schema_for(provider, class_type)) for class_type in sorted(node_classes))
        for class_type, schema in candidates:
            if schema is None:
                continue
            try:
                raw_schemas[str(class_type)] = schema_payload_from_node_schema(str(class_type), schema)
            except Exception as exc:
                raise _ArtifactExecutionError("schema snapshot", f"could not serialize {class_type!r}: {type(exc).__name__}: {exc}") from exc
    missing = sorted(class_type for class_type in node_classes if class_type not in raw_schemas)
    snapshot = capture_schema_snapshot(request_snapshot={"schemas": raw_schemas, "missing_classes": missing})
    return schema_snapshot_to_payload(snapshot)


def _new_entry(template_id: str, path: str, original: str, transformed: str) -> dict[str, Any]:
    return {
        "template_id": template_id,
        "path": path,
        "original_loc": len([line for line in original.splitlines() if line.strip()]),
        "emitted_loc": len([line for line in transformed.splitlines() if line.strip()]),
        "loc_delta": len([line for line in transformed.splitlines() if line.strip()]) - len([line for line in original.splitlines() if line.strip()]),
        "changed": transformed != original,
        "status": "pending",
        "parity_ok": None,
        "semantic_parity_ok": None,
        "conversion_parity_ok": None,
        "error": None,
    }


def simulate_rule(rule_spec: str, template_ids: list[str] | None = None, *, schema_provider: Any = None) -> SimulationResult:
    """Simulate a rule over admitted generated templates without monkeypatching Python."""
    try:
        rule_name, rule_value = _parse_rule_spec(rule_spec)
    except ValueError as exc:
        return SimulationResult(rule_spec, 0, 0, 0, 0, 0, error=str(exc))
    if rule_name not in _TRANSFORMS:
        return SimulationResult(rule_spec, 0, 0, 0, 0, 0, error=f"Unknown rule: {rule_name!r}. Available: {sorted(_TRANSFORMS)}")
    try:
        _apply_rule("", rule_name, rule_value)
    except ValueError as exc:
        return SimulationResult(rule_spec, 0, 0, 0, 0, 0, error=str(exc))

    caller_schema_provider = schema_provider
    if schema_provider is None:
        schema_provider = get_schema_provider("auto")
    snapshot = build_corpus_snapshot(_REPO_ROOT / "ready_templates")
    templates_by_id = {template["id"]: template for template in snapshot.templates_list}
    target_ids = (
        [template["id"] for template in snapshot.templates_list if template["marker"] == "generated"]
        if template_ids is None
        else list(dict.fromkeys(template_ids))
    )
    entries: list[dict[str, Any]] = []
    prepared: list[tuple[dict[str, Any], Path, str, str, TemplateAdmission, TemplateAdmission]] = []
    all_node_classes: set[str] = set()
    sample_diff = ""
    for tid in target_ids:
        template = templates_by_id.get(tid)
        if template is None:
            entries.append({"template_id": tid, "path": "", "original_loc": 0, "emitted_loc": 0, "loc_delta": 0, "changed": False, "status": "failed", "parity_ok": False, "semantic_parity_ok": None, "conversion_parity_ok": None, "error": f"template not found in corpus: {tid}"})
            continue
        path = Path(template["path"])
        try:
            original = path.read_text(encoding="utf-8")
        except OSError as exc:
            entries.append({"template_id": tid, "path": str(path), "original_loc": 0, "emitted_loc": 0, "loc_delta": 0, "changed": False, "status": "failed", "parity_ok": False, "semantic_parity_ok": None, "conversion_parity_ok": None, "error": f"source read failed: {type(exc).__name__}: {exc}"})
            continue
        transformed = _apply_rule(original, rule_name, rule_value)
        entry = _new_entry(tid, str(path), original, transformed)
        if transformed != original and not sample_diff:
            sample_diff = "".join(difflib.unified_diff(original.splitlines(keepends=True), transformed.splitlines(keepends=True), fromfile=str(path), tofile=f"{path} (simulated)"))
        original_admission = admit_template_source(original)
        transformed_admission = admit_template_source(transformed)
        if original_admission.status == "unsupported" and original_admission.reason and original_admission.reason["code"] == "syntax_error":
            entry.update(status="failed", parity_ok=False, error=original_admission.reason["message"])
        elif transformed_admission.status == "unsupported" and transformed_admission.reason and transformed_admission.reason["code"] == "syntax_error":
            entry.update(status="failed", parity_ok=False, error=transformed_admission.reason["message"])
        elif not original_admission.admitted:
            entry.update(status="unsupported", unsupported=original_admission.to_json(), parity_ok=None)
        elif not transformed_admission.admitted:
            entry.update(status="unsupported", unsupported=transformed_admission.to_json(), parity_ok=None)
        else:
            all_node_classes.update(original_admission.node_classes)
            all_node_classes.update(transformed_admission.node_classes)
            prepared.append((entry, path, original, transformed, original_admission, transformed_admission))
        entries.append(entry)

    try:
        schema_payload = _freeze_schema_snapshot(caller_schema_provider if caller_schema_provider is not None else schema_provider, all_node_classes)
        frozen_provider = schema_snapshot_provider_from_payload(schema_payload)
    except Exception as exc:
        return SimulationResult(rule_spec, len(entries), sum(bool(entry.get("changed")) for entry in entries), sum(int(entry.get("loc_delta", 0)) for entry in entries), 0, sum(1 for entry in entries if entry.get("status") == "failed"), sum(1 for entry in entries if entry.get("status") == "unsupported"), entries, sample_diff, f"schema snapshot failed: {type(exc).__name__}: {exc}")

    with tempfile.TemporaryDirectory(prefix="vibecomfy-port-simulate-") as tmp:
        for entry, path, original, transformed, _original_admission, _transformed_admission in prepared:
            artifact_paths: list[Path] = []
            transformed_payload: dict[str, Any] | None = None
            original_payload: dict[str, Any] | None = None
            failures: list[str] = []
            try:
                root = Path(tmp) / entry["template_id"].replace("/", "_")
                transformed_path = _materialize_transformed_source(path, transformed, root / "transformed")
                original_path = _materialize_transformed_source(path, original, root / "original")
                artifact_paths.extend((transformed_path, original_path))
                try:
                    transformed_payload = _run_artifact_worker(transformed_path, logical_path=path)
                except _ArtifactExecutionError as exc:
                    failures.append(f"transformed {exc.stage} failed: {exc}")
                try:
                    original_payload = _run_artifact_worker(original_path, logical_path=path)
                except _ArtifactExecutionError as exc:
                    failures.append(f"original {exc.stage} failed: {exc}")
                if failures:
                    entry.update(status="failed", parity_ok=False, error="; ".join(failures))
                    continue
                assert transformed_payload is not None and original_payload is not None
                entry["transformed_stdout"] = transformed_payload.get("stdout", "")
                entry["transformed_stdout_truncated"] = bool(transformed_payload.get("stdout_truncated", False))
                entry["original_stdout"] = original_payload.get("stdout", "")
                entry["original_stdout_truncated"] = bool(original_payload.get("stdout_truncated", False))
                semantic_ok, semantic_diffs = compile_equivalent(original_payload["api"], transformed_payload["api"])
                entry["semantic_parity_ok"] = semantic_ok
                if not entry["changed"]:
                    entry["conversion_parity_ok"] = True
                    entry["parity_ok"] = semantic_ok
                    entry["status"] = "ok" if semantic_ok else "failed"
                    if not semantic_ok:
                        entry["error"] = "transformed workflow diverged from original"
                    continue
                conversion = port_convert_workflow(
                    VibeWorkflow.from_envelope(transformed_payload["envelope"]),
                    source_path=str(path),
                    source_hash=None,
                    schema_provider=frozen_provider,
                    validate=True,
                )
                validation = conversion.validation
                conversion_ok = bool(isinstance(validation, object) and validation is not None and validation.ok and validation.parity_ok is True and validation.parity_error is None)
                entry["conversion_parity_ok"] = conversion_ok
                parity_diffs = list(semantic_diffs)
                if validation is not None:
                    parity_diffs.extend(f"conversion: {diff}" for diff in validation.parity_diffs)
                if parity_diffs:
                    entry["parity_diffs"] = parity_diffs
                entry["parity_ok"] = semantic_ok and conversion_ok
                entry["status"] = "ok" if entry["parity_ok"] else "failed"
                if entry["status"] == "failed":
                    errors: list[str] = []
                    if not semantic_ok:
                        errors.append("transformed workflow diverged from original")
                    if not conversion_ok:
                        detail = validation.parity_error if validation is not None else None
                        errors.append("transformed conversion parity failed" + (f": {detail}" if detail else ""))
                    entry["error"] = "; ".join(errors)
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                for artifact_path in artifact_paths:
                    detail = detail.replace(str(artifact_path), "<artifact>")
                entry.update(status="failed", parity_ok=False, error=detail)

    failed = sum(1 for entry in entries if entry.get("status") == "failed")
    unsupported = sum(1 for entry in entries if entry.get("status") == "unsupported")
    preserved = sum(1 for entry in entries if entry.get("status") == "ok")
    return SimulationResult(
        rule_spec=rule_spec,
        templates_total=len(entries),
        templates_affected=sum(1 for entry in entries if entry.get("changed") is True),
        loc_delta_total=sum(int(entry.get("loc_delta", 0)) for entry in entries),
        parity_preserved=preserved,
        parity_broken=failed,
        unsupported=unsupported,
        per_template=entries,
        sample_diff=sample_diff,
        schema_snapshot_digest=schema_payload.get("content_digest"),
    )


if __name__ == "__main__":
    if "--_artifact-worker" in sys.argv:
        raise SystemExit(_artifact_worker_main(sys.argv[1:]))
    if "--_artifact-exec" in sys.argv:
        raise SystemExit(_artifact_execution_main(sys.argv[1:]))
__all__ = [
    "SimulationPerTemplate",
    "SimulationResult",
    "TemplateAdmission",
    "admit_template_source",
    "simulate_rule",
]
