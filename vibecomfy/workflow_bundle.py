"""Canonical workflow source bundles.

This module is deliberately a small binding around :class:`VibeWorkflow`.
The workflow remains the only semantic authority; a bundle only records where
it was loaded from, the optional presentation candidate, and deterministic
digests for that candidate revision.  In particular, this is not an approval
or execution registry.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.security.provenance import Provenance
from vibecomfy.testing.canonical import canonical_digest
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


class WorkflowBundleError(ValueError):
    """Raised when a bundle cannot be loaded or fails a closed boundary."""


_IDENTITY_KEYS = frozenset(
    {
        "workflow_id",
        "workflow_identity",
        "source_id",
        "source_identity",
        "bind_id",
        "registry_id",
        "import_id",
        "capture_id",
    }
)
_CONTAINER_ID_KEYS = frozenset(
    {"source", "bind", "registry", "import", "capture", "lineage", "provenance"}
)
_OPERATIONS = frozenset({"authored", "imported", "captured"})


def _identity_declarations(value: Any, *, container: str = "") -> list[tuple[str, Any]]:
    """Find repeated identity declarations in source-shaped mappings.

    Native node/API dictionaries have many unrelated ``id`` fields, so plain
    ``id`` is intentionally considered only inside an explicitly named
    source/bind/registry/import/capture container.
    """
    found: list[tuple[str, Any]] = []
    if not isinstance(value, Mapping):
        return found
    for key, item in value.items():
        name = str(key)
        lowered = name.casefold()
        if lowered in _IDENTITY_KEYS:
            found.append((f"{container}.{name}" if container else name, item))
        elif lowered == "id" and container.casefold().rsplit(".", 1)[-1] in _CONTAINER_ID_KEYS:
            found.append((f"{container}.{name}", item))
        if isinstance(item, Mapping):
            next_container = name if lowered in _CONTAINER_ID_KEYS else container
            found.extend(_identity_declarations(item, container=next_container))
    return found


def _check_identity(workflow: VibeWorkflow, *declarations: Any) -> None:
    """Validate all known repeated identities before any digest/materialization."""
    report = workflow.validate_identity()
    if not report.ok:
        raise WorkflowBundleError(report.issues[0].message)

    values: list[tuple[str, Any]] = []
    values.extend(_identity_declarations(getattr(workflow, "metadata", {}), container="metadata"))
    values.extend(_identity_declarations(getattr(workflow.source, "provenance", {}), container="source.provenance"))
    for declaration in declarations:
        values.extend(_identity_declarations(declaration))
    for label, value in values:
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise WorkflowBundleError(f"{label} must be a nonblank workflow identity")
        if value != workflow.id:
            raise WorkflowBundleError(
                f"workflow identity mismatch: {label} {value!r} must equal {workflow.id!r}"
            )


def _first(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def filter_provenance(
    provenance: Any,
    *,
    default_operation: str,
) -> dict[str, Any]:
    """Return the closed, deterministic provenance object used by revisions.

    Operational timestamps, local paths, process/session identifiers and
    unknown extension keys are deliberately omitted.  An unsupported
    operation is an error, rather than a new implicit authority.
    """
    if not isinstance(default_operation, str) or default_operation not in _OPERATIONS:
        raise WorkflowBundleError(f"unsupported bundle operation {default_operation!r}")
    if provenance is None:
        raw: Mapping[str, Any] = {}
    elif isinstance(provenance, Mapping):
        raw = provenance
    elif isinstance(provenance, str) and provenance in {
        "user_confirmed",
        "agent_authored",
        "agent_generated",
        "untrusted_source",
    }:
        # Existing loader provenance tags are trust tags, not bundle metadata.
        # Keep the operation closed and avoid making the tag a revision input.
        raw = {}
    else:
        raise WorkflowBundleError(
            f"unsupported provenance value {type(provenance).__name__}; expected a mapping"
        )

    operation = _first(raw, "operation", "operation_kind", "kind")
    if operation is None:
        operation = default_operation
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        raise WorkflowBundleError(f"unsupported provenance operation {operation!r}")

    result: dict[str, Any] = {"operation": operation}
    origin = raw.get("origin")
    if isinstance(origin, Mapping):
        origin_kind = _first(origin, "kind", "origin_kind")
        origin_uri = _first(origin, "uri", "origin_uri")
    else:
        origin_kind = _first(raw, "origin_kind")
        origin_uri = _first(raw, "origin_uri", "uri")
    for key, value in (("origin_kind", origin_kind), ("origin_uri", origin_uri)):
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise WorkflowBundleError(f"provenance {key} must be a nonblank string")
            result[key] = value

    pin = _first(raw, "origin_pin", "immutable_origin_pin", "pin")
    source_digest = _first(raw, "source_digest", "origin_digest")
    for key, value in (("origin_pin", pin), ("source_digest", source_digest)):
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise WorkflowBundleError(f"provenance {key} must be a nonblank string")
            result[key] = value

    author = _first(raw, "author_id", "author")
    producer = _first(raw, "producer_id", "producer")
    for key, value in (("author_id", author), ("producer_id", producer)):
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise WorkflowBundleError(f"provenance {key} must be a nonblank string")
            result[key] = value

    tools = _first(raw, "tool_versions", "transformation_tool_versions", "tools")
    if tools is not None:
        # canonical_digest performs the strict JSON-value check.  Store a
        # detached value so caller mutation cannot change a returned bundle.
        try:
            canonical_digest(tools)
        except (TypeError, ValueError) as exc:
            raise WorkflowBundleError(f"invalid provenance tool_versions: {exc}") from exc
        result["tool_versions"] = copy.deepcopy(tools)
    return result


def _sidecar_path(source: Path) -> Path:
    return source.with_suffix(".vibe.json")


def _read_sidecar(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    candidate = _sidecar_path(path)
    if not candidate.is_file():
        return None
    try:
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowBundleError(f"could not read workflow sidecar {candidate}: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkflowBundleError("workflow sidecar must contain a JSON object")
    return raw


def _check_sidecar_identity(sidecar: Mapping[str, Any] | None, workflow: VibeWorkflow) -> None:
    if sidecar is None:
        return
    _check_identity(workflow, sidecar)
    bind = sidecar.get("bind")
    if bind is not None and not isinstance(bind, Mapping):
        raise WorkflowBundleError("workflow sidecar bind must be a mapping")


def _lineage_records(workflow: VibeWorkflow) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    sources = [getattr(workflow, "metadata", {}), getattr(workflow.source, "provenance", {})]
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key in ("revision_evidence",):
            value = source.get(key)
            if isinstance(value, Mapping):
                if isinstance(value.get("revision_id"), str):
                    records.append(value)
                else:
                    records.extend(item for item in value.values() if isinstance(item, Mapping))
            elif isinstance(value, (list, tuple)):
                records.extend(item for item in value if isinstance(item, Mapping))
    return records


def _resolve_parent(workflow: VibeWorkflow, parent_revision: str) -> str:
    if not isinstance(parent_revision, str):
        raise WorkflowBundleError("parent_revision must be a revision string")
    if not parent_revision:
        return ""
    for record in _lineage_records(workflow):
        if record.get("revision_id") != parent_revision:
            continue
        identity = record.get("workflow_identity", record.get("workflow_id"))
        if identity != workflow.id:
            raise WorkflowBundleError("parent revision workflow identity does not match child workflow")
        return parent_revision
    raise WorkflowBundleError(f"unknown parent revision {parent_revision!r}")


@dataclass(frozen=True)
class WorkflowBundle:
    """One candidate source revision bound to a :class:`VibeWorkflow`."""

    workflow: VibeWorkflow
    python_path: Path | None
    ui_sidecar: Mapping[str, Any] | None
    semantic_digest: str
    ui_digest: str
    provenance: Mapping[str, Any]
    parent_revision: str = ""
    revision_id: str = ""

    @property
    def workflow_identity(self) -> str:
        """Read-only identity derived from the workflow, never independently stored."""
        return self.workflow.id

def _make_bundle(
    workflow: VibeWorkflow,
    *,
    python_path: Path | None,
    ui_sidecar: Mapping[str, Any] | None,
    provenance: Any,
    operation: str,
    parent_revision: str = "",
) -> WorkflowBundle:
    # This ordering is intentional: identity checks precede sidecar checks,
    # semantic digesting, UI digesting, revision creation, and source writes.
    _check_identity(workflow, provenance, ui_sidecar)
    _check_sidecar_identity(ui_sidecar, workflow)
    semantic_digest = workflow.semantic_digest()
    sidecar = copy.deepcopy(dict(ui_sidecar)) if ui_sidecar is not None else None
    ui_digest = canonical_digest(sidecar) if sidecar is not None else ""
    filtered = filter_provenance(provenance, default_operation=operation)
    parent = _resolve_parent(workflow, parent_revision)
    revision_id = canonical_digest(
        [workflow.id, semantic_digest, ui_digest, filtered, parent]
    )
    bundle = WorkflowBundle(
        workflow=workflow,
        python_path=python_path,
        ui_sidecar=sidecar,
        semantic_digest=semantic_digest,
        ui_digest=ui_digest,
        provenance=filtered,
        parent_revision=parent,
        revision_id=revision_id,
    )
    return bundle


def _resolve_reference(reference: str | Path) -> tuple[str | Path, Path | None, str]:
    value = Path(reference) if isinstance(reference, Path) else Path(str(reference))
    if value.suffix.lower() == ".vibe.json":
        python = value.with_suffix("").with_suffix(".py")
        return python, python if python.is_file() else None, "authored"
    if value.is_file() and value.suffix.lower() in {".py", ".json"}:
        return value, value if value.suffix.lower() == ".py" else None, (
            "authored" if value.suffix.lower() == ".py" else "imported"
        )
    return str(reference), None, "authored"


def _import_identity(raw: Mapping[str, Any], *, source_kind: str) -> str:
    """Extract an authored identity before crossing a JSON import boundary."""
    source = raw.get("source")
    if source_kind == "ui":
        candidates = (_first(raw, "workflow_identity", "workflow_id", "id"),)
    else:
        candidates = (
            _first(raw, "workflow_identity", "workflow_id", "id"),
            _first(source, "id", "workflow_identity", "workflow_id")
            if isinstance(source, Mapping)
            else None,
        )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value
    raise WorkflowBundleError(
        "imported workflow has no explicit durable identity; add workflow_id "
        "(or an envelope source.id) before loading a canonical bundle"
    )


def load_bundle(reference: str | Path, trust: Provenance | None = None) -> WorkflowBundle:
    """Load one canonical Python/compatibility reference as a candidate bundle."""
    resolved, python_path, operation = _resolve_reference(reference)
    declared_identity: str | None = None
    if python_path is not None:
        from vibecomfy.scratchpad_loader import load_scratchpad

        # The compatibility CLI defaults to user confirmation.  Bundles keep
        # the actual typed trust value and let the restricted loader decide.
        workflow = load_scratchpad(python_path, provenance_override=trust)
    elif isinstance(resolved, Path) and resolved.suffix.lower() == ".json":
        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise WorkflowBundleError(f"could not read workflow source {resolved}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise WorkflowBundleError("imported workflow source must contain a JSON object")
        if isinstance(raw.get("nodes"), dict) and (
            "vibecomfy_format_version" in raw or isinstance(raw.get("compiled_api"), dict)
        ):
            source_kind = "envelope"
        elif isinstance(raw.get("nodes"), list):
            source_kind = "ui"
        else:
            source_kind = "api"
        declared_identity = _import_identity(raw, source_kind=source_kind)
        from vibecomfy.cli_loader import _load_workflow_path

        workflow = _load_workflow_path(resolved, workflow_id=declared_identity)
    else:
        from vibecomfy.cli_loader import load_workflow_any

        workflow = load_workflow_any(str(resolved))
        try:
            from vibecomfy.registry.ready import resolve_ready_template

            declared_identity = resolve_ready_template(str(reference)).template_id
        except (KeyError, ValueError):
            declared_identity = None
        source = getattr(workflow, "source", None)
        source_path = getattr(source, "path", None)
        if isinstance(source_path, str) and source_path:
            candidate = Path(source_path)
            if candidate.suffix.lower() == ".py":
                python_path = candidate
            elif candidate.suffix.lower() == ".json":
                operation = "imported"
    sidecar = _read_sidecar(python_path or (Path(resolved) if isinstance(resolved, Path) else None))
    source_provenance = getattr(getattr(workflow, "source", None), "provenance", {})
    # A ready/template reference is a declared identity, including aliases;
    # check it before any digesting so a registry stem cannot become identity.
    declarations = ({"workflow_identity": declared_identity},) if declared_identity else ()
    _check_identity(workflow, *declarations)
    return _make_bundle(
        workflow,
        python_path=python_path,
        ui_sidecar=sidecar,
        provenance=source_provenance,
        operation=operation,
    )


def _destination_path(destination: str | Path, workflow: VibeWorkflow) -> Path:
    path = Path(destination)
    if path.exists() and path.is_dir():
        return path / f"{workflow.id}.py"
    if path.suffix.lower() != ".py":
        return path / f"{workflow.id}.py"
    return path


def emit_bundle(
    workflow: VibeWorkflow,
    destination: str | Path,
    provenance: Any,
    parent_revision: str = "",
) -> WorkflowBundle:
    """Write a canonical ``build()`` source candidate and return its bundle."""
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"emit_bundle requires VibeWorkflow, got {type(workflow).__name__}")
    path = _destination_path(destination, workflow)
    # Preserve an already-present presentation candidate when replacing the
    # Python source.  Strict schema validation and atomic pair publication are
    # intentionally deferred to the sidecar owner (T04).
    existing_sidecar = _read_sidecar(path)
    bundle = _make_bundle(
        workflow,
        python_path=path,
        ui_sidecar=existing_sidecar,
        provenance=provenance,
        operation="authored",
        parent_revision=parent_revision,
    )
    from vibecomfy.porting.emit import emit_scratchpad_python

    path.parent.mkdir(parents=True, exist_ok=True)
    source = emit_scratchpad_python(
        workflow,
        workflow_id=workflow.id,
        source_path=str(path),
        provenance=dict(bundle.provenance),
    )
    path.write_text(source, encoding="utf-8")
    return bundle


def capture_bundle(
    ui_graph: Mapping[str, Any] | VibeWorkflow,
    destination: str | Path,
    provenance: Any,
    parent_revision: str = "",
) -> WorkflowBundle:
    """Convert a captured UI/API graph into a candidate canonical revision."""
    if isinstance(ui_graph, VibeWorkflow):
        workflow = ui_graph
        candidate: Mapping[str, Any] | None = None
    elif isinstance(ui_graph, Mapping):
        # The provisional path is only used to pass the source location to
        # the compatibility importer; the imported workflow id is authoritative.
        destination_path = Path(destination)
        if destination_path.suffix.lower() != ".py":
            destination_path = destination_path / "capture.py"
        if isinstance(ui_graph.get("nodes"), dict) and (
            "vibecomfy_format_version" in ui_graph or isinstance(ui_graph.get("compiled_api"), dict)
        ):
            source_kind = "envelope"
        elif isinstance(ui_graph.get("nodes"), list):
            source_kind = "ui"
        else:
            source_kind = "api"
        declared = _import_identity(ui_graph, source_kind=source_kind)
        from vibecomfy.ingest.normalize import _named_import

        workflow = _named_import(
            dict(ui_graph),
            source_path=str(destination_path),
            workflow_id=declared,
        )
        candidate = ui_graph
    else:
        raise TypeError(f"capture_bundle requires a UI mapping, got {type(ui_graph).__name__}")
    return emit_bundle_with_candidate(
        workflow,
        destination,
        provenance,
        candidate,
        parent_revision=parent_revision,
        operation="captured",
    )


def emit_bundle_with_candidate(
    workflow: VibeWorkflow,
    destination: str | Path,
    provenance: Any,
    candidate: Mapping[str, Any] | None,
    *,
    parent_revision: str = "",
    operation: str = "authored",
) -> WorkflowBundle:
    """Internal shared writer for emit/capture candidate bundles."""
    path = _destination_path(destination, workflow)
    bundle = _make_bundle(
        workflow,
        python_path=path,
        ui_sidecar=candidate,
        provenance=provenance,
        operation=operation,
        parent_revision=parent_revision,
    )
    from vibecomfy.porting.emit import emit_scratchpad_python

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        emit_scratchpad_python(
            workflow,
            workflow_id=workflow.id,
            source_path=str(path),
            provenance=dict(bundle.provenance),
        ),
        encoding="utf-8",
    )
    return bundle


__all__ = [
    "WorkflowBundle",
    "WorkflowBundleError",
    "capture_bundle",
    "emit_bundle",
    "filter_provenance",
    "load_bundle",
]
