from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
import importlib.util
from pathlib import Path
import warnings
from typing import Any, Iterable

from vibecomfy.errors import WorkflowBuildError
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.security.agent_generated_loader import ScanReport, scan_agent_generated_python
from vibecomfy.security import current_gate_context, require_confirmation
from vibecomfy.security.loader_provenance import _provenance_for_path
from vibecomfy.utils import find_repo_root
from vibecomfy.workflow import VibeWorkflow


READY_ROOT = find_repo_root() / "ready_templates"
_WARNED_COLLISIONS: set[str] = set()


class ReadyTemplateLoadError(WorkflowBuildError):
    """Raised when a dynamic ready template fails the pre-execution scan."""

    def __init__(self, message: str, *, report: ScanReport) -> None:
        self.report = report
        super().__init__(
            message,
            next_action=(
                "Remove unsafe Python from the dynamic ready template or move the code into a packaged built-in template."
            ),
        )

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["report"] = self.report.to_dict()
        return payload


@dataclass(frozen=True)
class ReadyTemplateSourceInfo:
    """Source classification for a ready template."""

    template_id: str
    path: str
    source_mode: str
    runtime_source_of_truth: bool
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def repo_ready_template_paths(root: Path | None = None) -> list[Path]:
    """Return checked-in repo ready-template paths without loading plugins."""
    return _template_paths(root or READY_ROOT)


def repo_ready_template_id_for_path(path: Path, root: Path | None = None) -> str:
    """Return the ready-template id for a path under the repo ready root."""
    return path.relative_to(root or READY_ROOT).with_suffix("").as_posix()


def repo_ready_template_ids(root: Path | None = None) -> list[str]:
    """Return checked-in repo ready-template ids without loading plugins."""
    ready_root = root or READY_ROOT
    return sorted(repo_ready_template_id_for_path(path, ready_root) for path in repo_ready_template_paths(ready_root))


def dynamic_ready_template_rows(*, exclude_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Return explicitly discovered plugin/user ready-template rows."""
    excluded = set(exclude_ids)
    seen: dict[str, Path] = {}
    rows: list[dict[str, Any]] = []
    for root in _dynamic_ready_roots():
        if not root.exists():
            continue
        for path in _template_paths(root):
            template_id = path.relative_to(root).with_suffix("").as_posix()
            if template_id in excluded:
                continue
            if template_id in seen:
                _warn_collision(template_id, path, seen[template_id])
                continue
            seen[template_id] = path
            rows.append(
                {
                    "id": template_id,
                    "path": str(path),
                    "source_scope": "dynamic",
                    "indexed": False,
                }
            )
    return sorted(rows, key=lambda row: row["id"])


def ready_template_ids(*, include_dynamic: bool = True) -> list[str]:
    seen: dict[str, Path] = {}
    roots = _ready_roots() if include_dynamic else [READY_ROOT]
    for root in roots:
        if not root.exists():
            continue
        for path in _template_paths(root):
            template_id = path.relative_to(root).with_suffix("").as_posix()
            if template_id in seen:
                _warn_collision(template_id, path, seen[template_id])
                continue
            seen[template_id] = path
    return sorted(seen)


def workflow_from_ready(template_id: str) -> VibeWorkflow:
    path = _resolve_ready_path(template_id)
    is_dynamic_ready_template = _path_is_dynamic_ready_template(path)
    if is_dynamic_ready_template:
        _scan_dynamic_ready_template(path)
    spec = importlib.util.spec_from_file_location(f"vibecomfy_ready_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not import ready template {path}")
    module = importlib.util.module_from_spec(spec)
    provenance = _provenance_for_path(path)
    if provenance == "untrusted_source" and is_dynamic_ready_template:
        provenance = "user_confirmed"
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
        raise ValueError(f"Ready template {template_id} must define build()")
    workflow = build()
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"Ready template {template_id} build() must return VibeWorkflow, got {type(workflow).__name__}")
    resolved_template_id = _template_id_for_path(path)
    if not workflow.metadata.get("python_policy_applied"):
        ready_metadata = getattr(module, "READY_METADATA", None)
        if isinstance(ready_metadata, dict):
            ready_metadata = {**ready_metadata, "ready_template": ready_metadata.get("ready_template") or resolved_template_id}
            requirements = getattr(module, "READY_REQUIREMENTS", None)
            workflow = apply_ready_template_policy(
                workflow,
                ready_metadata,
                source_path=str(path),
                requirements=requirements if isinstance(requirements, dict) else None,
            )
    workflow.metadata["ready_template"] = workflow.metadata.get("ready_template") or resolved_template_id
    return workflow


def ready_template_source_info(template_id: str) -> ReadyTemplateSourceInfo:
    """Classify a ready template's runtime source mode.

    ``pure_python`` means the ready template builds a ``VibeWorkflow`` directly
    and does not load JSON/API dictionaries at runtime. API-dict or JSON
    wrappers are reported as diagnostics because app-active templates should
    not use them as runtime source of truth.
    """
    path = _resolve_ready_path(template_id)
    diagnostics: list[dict[str, Any]] = []
    source_mode = "unknown"
    runtime_source_of_truth = False
    if path.suffix.lower() == ".json":
        source_mode = "json_reference"
        diagnostics.append(
            {
                "code": "json_runtime_source",
                "severity": "error",
                "message": "Ready template resolves to JSON; runtime source must be pure Python.",
            }
        )
    else:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            source_mode = "invalid_python"
            diagnostics.append(
                {
                    "code": "syntax_error",
                    "severity": "error",
                    "message": str(exc),
                }
            )
        else:
            findings = _classify_ready_template_ast(tree)
            source_mode = findings["source_mode"]
            runtime_source_of_truth = bool(findings["runtime_source_of_truth"])
            diagnostics.extend(findings["diagnostics"])
    return ReadyTemplateSourceInfo(
        template_id=template_id,
        path=str(path),
        source_mode=source_mode,
        runtime_source_of_truth=runtime_source_of_truth,
        diagnostics=diagnostics,
    )


def _classify_ready_template_ast(tree: ast.AST) -> dict[str, Any]:
    has_build = False
    constructs_vibeworkflow = False
    forks_ready_workflow = False
    applies_ready_policy = False
    loads_json_runtime = False
    api_dict_wrapper = False
    diagnostics: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build":
            has_build = True
        if isinstance(node, ast.Call):
            call_name = _ast_call_name(node.func)
            if call_name.endswith("VibeWorkflow") or call_name == "new_workflow":
                constructs_vibeworkflow = True
            if call_name == "workflow_from_ready":
                forks_ready_workflow = True
            if call_name in {"apply_ready_template_policy", "finalize_ready"}:
                applies_ready_policy = True
            if call_name in {"json.load", "json.loads", "load_workflow_json", "load_template"}:
                loads_json_runtime = True
            if call_name.endswith(".compile") or call_name in {"convert_to_vibe_format", "workflow_from_api"}:
                api_dict_wrapper = True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.upper() in {"API", "API_DICT", "WORKFLOW_JSON"}:
                    api_dict_wrapper = True
    if not has_build:
        diagnostics.append(
            {
                "code": "missing_build",
                "severity": "error",
                "message": "Ready template must define build().",
            }
        )
    if loads_json_runtime:
        diagnostics.append(
            {
                "code": "json_runtime_load",
                "severity": "error",
                "message": "Template loads JSON at runtime; JSON may only be reference/corpus material.",
            }
        )
    if api_dict_wrapper:
        diagnostics.append(
            {
                "code": "api_dict_runtime_wrapper",
                "severity": "error",
                "message": "Template appears to wrap an API dict at runtime instead of building pure Python workflow source.",
            }
        )
    if (
        (constructs_vibeworkflow or (forks_ready_workflow and applies_ready_policy))
        and not loads_json_runtime
        and not api_dict_wrapper
        and has_build
    ):
        source_mode = "pure_python"
        runtime_source_of_truth = True
    elif loads_json_runtime:
        source_mode = "json_runtime_wrapper"
        runtime_source_of_truth = False
    elif api_dict_wrapper:
        source_mode = "api_dict_wrapper"
        runtime_source_of_truth = False
    else:
        source_mode = "unknown"
        runtime_source_of_truth = False
    return {
        "source_mode": source_mode,
        "runtime_source_of_truth": runtime_source_of_truth,
        "diagnostics": diagnostics,
    }


def _ast_call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        prefix = _ast_call_name(func.value)
        return f"{prefix}.{func.attr}" if prefix else func.attr
    return ""


def _resolve_ready_path(template_id: str) -> Path:
    for root in _ready_roots():
        candidates = [
            root / f"{template_id}.py",
            root / template_id,
        ]
        if "/" not in template_id and root.exists():
            candidates.extend(root.glob(f"*/{template_id}.py"))
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    raise KeyError(f"Ready template not found: {template_id}")


def _scan_dynamic_ready_template(path: Path) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowBuildError(
            f"Could not read dynamic ready template {path}: {exc}",
            next_action="Verify the dynamic ready template file exists and is readable, then try again.",
        ) from exc
    report = scan_agent_generated_python(source)
    if not report.ok:
        raise ReadyTemplateLoadError(
            f"Dynamic ready template failed load_python scan: {path}",
            report=report,
        )


def _template_id_for_path(path: Path) -> str:
    resolved = path.resolve()
    for root in _ready_roots():
        try:
            return resolved.relative_to(root.resolve()).with_suffix("").as_posix()
        except ValueError:
            continue
    return path.with_suffix("").name


def _path_is_dynamic_ready_template(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    for root in _dynamic_ready_roots():
        try:
            if resolved.is_relative_to(root.resolve()):
                return True
        except (ValueError, OSError):
            continue
    return False


def _ready_roots() -> list[Path]:
    return _dedupe_roots([READY_ROOT, *_dynamic_ready_roots()])


def _dynamic_ready_roots() -> list[Path]:
    from vibecomfy.extras import ensure_plugins_loaded, registered_ready_roots

    ensure_plugins_loaded()
    return _dedupe_roots(
        [
            Path.cwd() / "vibecomfy_extras" / "ready_templates",
            Path.home() / ".vibecomfy" / "ready_templates",
            *registered_ready_roots(),
        ]
    )


def _dedupe_roots(roots: Iterable[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.expanduser().resolve()
        if resolved not in seen:
            deduped.append(resolved)
            seen.add(resolved)
    return deduped


def _template_paths(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if path.name != "__init__.py" and not path.name.startswith("_")
    )


def _warn_collision(template_id: str, candidate: Path, winner: Path) -> None:
    if template_id in _WARNED_COLLISIONS:
        return
    warnings.warn(
        f"Ready template id collision for {template_id!r}; using {winner} and ignoring {candidate}",
        RuntimeWarning,
        stacklevel=2,
    )
    _WARNED_COLLISIONS.add(template_id)


def _reset_for_tests() -> None:
    _WARNED_COLLISIONS.clear()
