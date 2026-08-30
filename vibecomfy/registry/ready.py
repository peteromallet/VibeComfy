from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
import importlib.util
from pathlib import Path
import unicodedata
from typing import Any, Iterable

from vibecomfy.errors import WorkflowBuildError
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.security.agent_generated_loader import ScanReport, scan_agent_generated_python
from vibecomfy.security import current_gate_context, require_confirmation
from vibecomfy.security.loader_provenance import _provenance_for_path
from vibecomfy.utils import find_repo_root
from vibecomfy.workflow import VibeWorkflow


def repo_ready_template_root() -> Path:
    """Return the checkout-only ready-template corpus root lazily."""
    return find_repo_root() / "ready_templates"


def __getattr__(name: str) -> Path:
    """Keep the historical READY_ROOT name lazy for checkout callers."""
    if name == "READY_ROOT":
        return repo_ready_template_root()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


@dataclass(frozen=True)
class ReadyTemplateRecord:
    """One enumerated ready template and its physical discovery scope."""

    template_id: str
    path: Path
    source_scope: str
    root: Path


@dataclass(frozen=True)
class ReadyTemplateDiscovery:
    """One physical ready-template discovery snapshot."""

    roots: tuple[Path, ...]
    records: tuple[ReadyTemplateRecord, ...]
    by_id: dict[str, tuple[ReadyTemplateRecord, ...]]
    by_lookup: dict[str, tuple[ReadyTemplateRecord, ...]]
    # Reference assets share this physical snapshot but are intentionally not
    # executable ready-template records or ids.
    reference_records: tuple[ReadyTemplateRecord, ...] = ()
    references_by_id: dict[str, tuple[ReadyTemplateRecord, ...]] = field(default_factory=dict)
    references_by_lookup: dict[str, tuple[ReadyTemplateRecord, ...]] = field(default_factory=dict)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.by_id, key=_id_sort_key))


def repo_ready_template_paths(root: Path | None = None) -> list[Path]:
    """Return checked-in repo ready-template paths without loading plugins."""
    return [record.path for record in _discover_ready_templates(roots=[root or repo_ready_template_root()]).records]


def repo_ready_template_id_for_path(path: Path, root: Path | None = None) -> str:
    """Return the enumerated ready-template id for a path under the repo root."""
    return _template_id_for_path(path, root or repo_ready_template_root())


def repo_ready_template_ids(root: Path | None = None) -> list[str]:
    """Return checked-in repo ready-template ids without loading plugins."""
    discovery = _discover_ready_templates(roots=[root or repo_ready_template_root()])
    _raise_duplicate_ids(discovery)
    return list(discovery.ids)


def _normalize_ready_template_id(template_id: str) -> str:
    """Normalize query separators and Unicode without changing filesystem case."""
    return unicodedata.normalize("NFC", str(template_id).replace("\\", "/"))


def _ready_lookup_key(template_id: str) -> str:
    """Return the case-folded lookup key for a canonical or query id."""
    return _normalize_ready_template_id(template_id).casefold()


def _normalized_path_key(path: Path) -> str:
    """Return a deterministic path sort key without becoming path identity."""
    return unicodedata.normalize("NFC", str(path)).casefold()


def _id_sort_key(template_id: str) -> tuple[str, str]:
    return (_ready_lookup_key(template_id), template_id)


def dynamic_ready_template_rows(*, exclude_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Return explicitly discovered plugin/user ready-template rows."""
    excluded = {_ready_lookup_key(template_id) for template_id in exclude_ids}
    discovery = _discover_ready_templates()
    rows = [
        {
            "id": record.template_id,
            "path": str(record.path),
            "source_scope": "dynamic",
            "indexed": False,
        }
        for record in discovery.records
        if record.source_scope == "dynamic" and _ready_lookup_key(record.template_id) not in excluded
    ]
    for lookup_key, all_records in discovery.by_lookup.items():
        records = tuple(record for record in all_records if record.source_scope == "dynamic")
        matching_rows = [
            row for row in rows if _ready_lookup_key(str(row["id"])) == lookup_key
        ]
        if len(matching_rows) < 2:
            continue
        details = _collision_details(min((record.template_id for record in records), key=_id_sort_key), records)
        for row in matching_rows:
            row.update(details)
    return sorted(rows, key=lambda row: _id_sort_key(str(row["id"])))



def ready_template_ids(*, include_dynamic: bool = True) -> list[str]:
    discovery = _discover_ready_templates(include_dynamic=include_dynamic)
    _raise_duplicate_ids(discovery)
    return list(discovery.ids)


def _discover_ready_templates(
    *,
    roots: Iterable[Path] | None = None,
    include_dynamic: bool = True,
    include_json_references: bool = True,
) -> ReadyTemplateDiscovery:
    selected_roots = list(roots) if roots is not None else (
        _ready_roots() if include_dynamic else [repo_ready_template_root()]
    )
    canonical_roots = tuple(_dedupe_roots(selected_roots))
    records: list[ReadyTemplateRecord] = []
    reference_records: list[ReadyTemplateRecord] = []
    for root in canonical_roots:
        source_scope = "repo" if _roots_are_same(root, _canonical_root(repo_ready_template_root())) else "dynamic"
        for path in _template_paths(root, include_json_references=include_json_references):
            record = ReadyTemplateRecord(
                # JSON files are corpus/reference assets, not executable
                # ready-template ids. Preserve their suffix so source-info can
                # resolve the existing ``foo.json`` spelling.
                template_id=_template_id_for_path(
                    path,
                    root,
                    preserve_suffix=include_json_references and path.suffix.lower() == ".json",
                ),
                path=path,
                source_scope=source_scope,
                root=root,
            )
            (reference_records if path.suffix.lower() == ".json" else records).append(record)
    records.sort(key=lambda record: (_id_sort_key(record.template_id), _path_sort_key(record.path)))
    reference_records.sort(key=lambda record: (_id_sort_key(record.template_id), _path_sort_key(record.path)))
    by_id: dict[str, list[ReadyTemplateRecord]] = {}
    by_lookup: dict[str, list[ReadyTemplateRecord]] = {}
    for record in records:
        by_id.setdefault(record.template_id, []).append(record)
        by_lookup.setdefault(_ready_lookup_key(record.template_id), []).append(record)
    references_by_id: dict[str, list[ReadyTemplateRecord]] = {}
    references_by_lookup: dict[str, list[ReadyTemplateRecord]] = {}
    for record in reference_records:
        references_by_id.setdefault(record.template_id, []).append(record)
        references_by_lookup.setdefault(_ready_lookup_key(record.template_id), []).append(record)
    return ReadyTemplateDiscovery(
        roots=canonical_roots,
        records=tuple(records),
        by_id={key: tuple(value) for key, value in sorted(by_id.items(), key=lambda item: _id_sort_key(item[0]))},
        by_lookup={key: tuple(value) for key, value in sorted(by_lookup.items())},
        reference_records=tuple(reference_records),
        references_by_id={
            key: tuple(value)
            for key, value in sorted(references_by_id.items(), key=lambda item: _id_sort_key(item[0]))
        },
        references_by_lookup={key: tuple(value) for key, value in sorted(references_by_lookup.items())},
    )
def ready_template_discovery(
    *,
    roots: Iterable[Path] | None = None,
    include_dynamic: bool = True,
    include_json_references: bool = True,
) -> ReadyTemplateDiscovery:
    """Return one physical ready-template discovery snapshot."""
    return _discover_ready_templates(
        roots=roots,
        include_dynamic=include_dynamic,
        include_json_references=include_json_references,
    )


def resolve_ready_template(
    template_id: str,
    discovery: ReadyTemplateDiscovery | None = None,
) -> ReadyTemplateRecord:
    """Resolve a ready-template alias against one discovery snapshot."""
    return _resolve_ready_record(template_id, discovery)


def repo_ready_template_discovery(root: Path | None = None) -> ReadyTemplateDiscovery:
    return _discover_ready_templates(roots=[root or repo_ready_template_root()])


def _raise_duplicate_ids(discovery: ReadyTemplateDiscovery) -> None:
    for template_id, records in discovery.by_id.items():
        if len(records) > 1:
            raise ValueError(_collision_message(template_id, records))




def workflow_from_ready(
    template_id: str,
    *,
    _discovery: ReadyTemplateDiscovery | None = None,
) -> VibeWorkflow:
    record = _resolve_ready_record(template_id, _discovery)
    path = record.path
    is_dynamic_ready_template = record.source_scope == "dynamic"
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
        class_type=None,  # type: ignore[arg-type]
        operation="scratchpad_exec",
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
    resolved_template_id = record.template_id
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


def ready_template_source_info(
    template_id: str,
    *,
    _discovery: ReadyTemplateDiscovery | None = None,
) -> ReadyTemplateSourceInfo:
    """Classify a ready template using one physical discovery snapshot.

    ``pure_python`` means the ready template builds a ``VibeWorkflow`` directly
    and does not load JSON/API dictionaries at runtime. API-dict or JSON
    wrappers are reported as diagnostics because app-active templates should
    not use them as runtime source of truth.
    """
    # Source-info retains the historical ``path/to/reference.json`` API, but
    # resolves it through the same physical enumeration as other consumers.
    # A caller-supplied snapshot is authoritative and must include references
    # when JSON is needed.
    discovery = _discovery or _discover_ready_templates(include_json_references=True)
    try:
        record = _resolve_ready_record(template_id, discovery)
    except KeyError:
        record = _resolve_ready_reference_record(template_id, discovery)
    path = record.path
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
        except (OSError, UnicodeError) as exc:
            source_mode = "unreadable"
            diagnostics.append(
                {
                    "code": "source_unreadable",
                    "severity": "error",
                    "message": f"Could not read ready template source: {type(exc).__name__}: {exc}",
                    "error_type": type(exc).__name__,
                }
            )
        else:
            findings = _classify_ready_template_ast(tree)
            source_mode = findings["source_mode"]
            runtime_source_of_truth = bool(findings["runtime_source_of_truth"])
            diagnostics.extend(findings["diagnostics"])
    return ReadyTemplateSourceInfo(
        template_id=record.template_id,
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
            if call_name.endswith(".compile") or call_name in {"from_api", "workflow_from_api"}:
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


def _resolve_ready_path(
    template_id: str,
    discovery: ReadyTemplateDiscovery | None = None,
) -> Path:
    return _resolve_ready_record(template_id, discovery).path


def _resolve_ready_record(
    template_id: str,
    discovery: ReadyTemplateDiscovery | None = None,
) -> ReadyTemplateRecord:
    query_id = _normalize_ready_template_id(template_id)
    discovery = discovery or _discover_ready_templates()
    exact_candidates = list(discovery.by_id.get(query_id, ())) if "/" in query_id else []
    if exact_candidates:
        if len(exact_candidates) > 1:
            raise ValueError(_collision_message(query_id, exact_candidates))
        return exact_candidates[0]
    if "/" in query_id:
        candidates = list(discovery.by_lookup.get(_ready_lookup_key(query_id), ()))
    else:
        lookup_key = _ready_lookup_key(query_id)
        candidates = [
            record
            for record in discovery.records
            if _ready_lookup_key(record.template_id.rsplit("/", 1)[-1]) == lookup_key
        ]
    if not candidates:
        raise KeyError(f"Ready template not found: {template_id}")
    candidate_ids = {record.template_id for record in candidates}
    if len(candidate_ids) > 1 or len(candidates) > 1:
        raise ValueError(_collision_message(query_id, candidates))
    return candidates[0]


def _resolve_ready_reference_record(
    template_id: str,
    discovery: ReadyTemplateDiscovery,
) -> ReadyTemplateRecord:
    """Resolve a corpus JSON reference from the same discovery snapshot."""
    query_id = _normalize_ready_template_id(template_id)
    exact = list(discovery.references_by_id.get(query_id, ())) if "/" in query_id else []
    if exact:
        if len(exact) > 1:
            raise ValueError(_collision_message(query_id, exact))
        return exact[0]
    candidates = list(discovery.references_by_lookup.get(_ready_lookup_key(query_id), ()))
    if not candidates:
        raise KeyError(f"Ready template not found: {template_id}")
    if len(candidates) > 1:
        raise ValueError(_collision_message(query_id, candidates))
    return candidates[0]

def _collision_details(
    query_id: str,
    records: Iterable[ReadyTemplateRecord],
) -> dict[str, Any]:
    records = tuple(records)
    candidates = sorted(
        {str(record.path) for record in records},
        key=lambda path: (_normalized_path_key(Path(path)), path),
    )
    candidate_ids = {record.template_id for record in records}
    if len(candidate_ids) == 1:
        remediation = "Remove the duplicate or use one canonical source."
    elif "/" in query_id:
        remediation = "Use the exact canonical id."
    else:
        remediation = "Use a category-qualified id."
    message = (
        f"Ambiguous ready template id {query_id!r}; candidates: "
        + ", ".join(candidates)
        + f". {remediation}"
    )
    return {
        "collision": True,
        "collision_candidates": candidates,
        "collision_message": message,
        "resolution_status": "collision",
    }

def _collision_message(query_id: str, records: Iterable[ReadyTemplateRecord]) -> str:
    return _collision_details(query_id, records)["collision_message"]


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


def _template_id_for_path(
    path: Path,
    root: Path | None = None,
    *,
    preserve_suffix: bool = False,
) -> str:
    root = root or repo_ready_template_root()
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path.resolve().relative_to(root.resolve())
    value = relative if preserve_suffix else relative.with_suffix("")
    return _normalize_ready_template_id(value.as_posix())


def _ready_roots() -> list[Path]:
    return _dedupe_roots([repo_ready_template_root(), *_dynamic_ready_roots()])


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


def _roots_are_same(left: Path, right: Path) -> bool:
    try:
        return left.resolve().samefile(right.resolve())
    except OSError:
        return False


def _canonical_root(root: Path) -> Path:
    """Recover stable directory-entry spelling for an existing root."""
    resolved = root.expanduser().resolve()
    if not resolved.exists():
        return Path(unicodedata.normalize("NFC", str(resolved)))
    current = Path(resolved.anchor)
    for component in resolved.parts[1:]:
        desired = current / component
        matches: list[Path] = []
        try:
            for child in current.iterdir():
                if child.name == component:
                    matches.append(child)
                    continue
                try:
                    if child.samefile(desired):
                        matches.append(child)
                except OSError:
                    continue
        except OSError:
            return Path(unicodedata.normalize("NFC", str(resolved)))
        if matches:
            current = min(matches, key=_path_sort_key)
        else:
            current = desired
    return current


def _dedupe_roots(roots: Iterable[Path]) -> list[Path]:
    deduped: list[Path] = []
    for root in roots:
        canonical = _canonical_root(root)
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(deduped)
                if (
                    existing.exists()
                    and canonical.exists()
                    and _roots_are_same(existing, canonical)
                )
                or (
                    not existing.exists()
                    and not canonical.exists()
                    and str(existing) == str(canonical)
                )
            ),
            None,
        )
        if duplicate_index is None:
            deduped.append(canonical)
        else:
            deduped[duplicate_index] = min(
                deduped[duplicate_index],
                canonical,
                key=_path_sort_key,
            )
    return sorted(deduped, key=_path_sort_key)


def _template_paths(root: Path, *, include_json_references: bool = False) -> list[Path]:
    suffixes = ("*.py", "*.json") if include_json_references else ("*.py",)
    paths = [path for suffix in suffixes for path in root.rglob(suffix)]
    return sorted(
        (
            path
            for path in paths
            if (path.suffix.lower() == ".json" or path.name != "__init__.py")
            and not path.name.startswith("_")
        ),
        key=_path_sort_key,
    )


def _path_sort_key(path: Path) -> tuple[str, str]:
    text = str(path)
    return _normalized_path_key(path), text




def _reset_for_tests() -> None:
    pass
