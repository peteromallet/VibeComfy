"""Canonical local edit/capture transitions for workflow bundles.

The service is deliberately an adapter around the existing typed edit
kernel and canonical bundle publisher. It retains no second graph model.
"""

from __future__ import annotations

import ast
import hashlib
import json
import tempfile
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.security import CapabilityFenceError
from vibecomfy.workflow_bundle import (
    WorkflowBundle,
    WorkflowBundleError,
    _build_v2_sidecar,
    _generated_metadata_expressions,
    _import_identity,
    _resolve_reference,
    _sidecar_path,
    _sidecar_ui_digest,
    _migrate_legacy_sidecar,
    _source_provenance,
    _split_import_api,
    _validate_v2_marker,
    _v2_marker,
    emit_bundle_with_candidate,
    load_bundle,
    validate_sidecar,
)


class BundleTransitionError(ValueError):
    """A bundle edit/capture could not be safely applied or published."""


@dataclass(frozen=True, slots=True)
class BundleTransitionResult:
    """Structured result of one accepted edit, manual capture, or preview."""

    status: str
    kind: str
    input_path: str
    python_path: str
    companion_path: str
    source_archive_path: str | None
    parent_revision: str | None
    revision_id: str
    before_semantic_digest: str | None
    semantic_digest: str
    before_ui_digest: str | None
    ui_digest: str
    operations: tuple[Mapping[str, Any], ...]
    diff: tuple[Mapping[str, Any], ...] | None
    diagnostics: tuple[Mapping[str, Any], ...]
    tracking: str = "untracked"

    @property
    def wrote_files(self) -> bool:
        return self.status == "saved"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "kind": self.kind,
            "tracking": self.tracking,
            "input": self.input_path,
            "python": self.python_path,
            "companion": self.companion_path,
            "source_archive": self.source_archive_path,
            "parent_revision": self.parent_revision,
            "revision": self.revision_id,
            "baseline": "known" if self.parent_revision is not None else "unknown",
            "diff_status": (
                "available" if self.diff is not None
                else "unavailable" if self.kind == "python_capture"
                else "not_applicable"
            ),
            "before": {
                "semantic_digest": self.before_semantic_digest,
                "ui_digest": self.before_ui_digest,
            },
            "after": {
                "semantic_digest": self.semantic_digest,
                "ui_digest": self.ui_digest,
            },
            "operations": [_jsonable(item) for item in self.operations],
            "diff": None if self.diff is None else [_jsonable(item) for item in self.diff],
            "diagnostics": [_jsonable(item) for item in self.diagnostics],
            "wrote_files": self.wrote_files,
        }


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def _digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _has_v2_source_marker(payload: bytes | None) -> bool:
    if payload is None:
        return False
    try:
        _expressions, values = _generated_metadata_expressions(payload)
    except WorkflowBundleError:
        return False
    return isinstance(values.get("source_bundle"), Mapping)


def _is_canonical_python_source(bundle: WorkflowBundle, python_path: Path) -> bool:
    """Return whether the source is exactly a VibeComfy-rendered representation.

    Typed/UI edits regenerate Python from the canonical IR. Refuse that rewrite
    when a user has added executable Python that the IR cannot represent.
    Compare the source outside its generated metadata assignment with both
    canonical renderers. Imported scratchpads and ready templates can carry
    different provenance in that call, but their graph-building code must
    still match one of VibeComfy's canonical renderers.
    """
    try:
        actual = python_path.read_bytes()
        workflow = bundle.workflow.copy()
        legacy_source = not (
            isinstance(bundle.ui_sidecar, Mapping)
            and bundle.ui_sidecar.get("format_version") == 2
        )
        if not legacy_source:
            workflow.metadata["source_bundle"] = _v2_marker(bundle.ui_sidecar)
        provenance = _source_provenance(bundle.provenance)
        from vibecomfy.porting.emit import emit_scratchpad_python

        scratchpad = emit_scratchpad_python(
            workflow,
            workflow_id=workflow.id,
            source_path=str(python_path),
            provenance=provenance,
            external_custody=True,
        ).encode("utf-8") if not legacy_source else emit_scratchpad_python(
            workflow,
            workflow_id=workflow.id,
            source_path=str(python_path),
            provenance=provenance,
            external_custody=False,
        ).encode("utf-8")

        # Legacy generated sources carry their verified execution custody in
        # constructor/finalize metadata rather than a v2 companion marker.
        # Compare the whole source before allowing an IR rewrite; only the
        # modern v2 path has a generated marker that can be replaced in place.
        if legacy_source:
            return actual == scratchpad

        expected_marker = _v2_marker(bundle.ui_sidecar)

        def normalized_source(source: bytes) -> tuple[dict[str, str], bytes]:
            module = ast.parse(source)

            def target_binds_metadata(target: ast.AST) -> bool:
                if isinstance(target, ast.Name):
                    return target.id == "READY_METADATA"
                if isinstance(target, (ast.Tuple, ast.List)):
                    return any(target_binds_metadata(item) for item in target.elts)
                return False

            def is_metadata_assignment(statement: ast.stmt) -> bool:
                if isinstance(statement, ast.Assign):
                    targets = statement.targets
                elif isinstance(statement, ast.AnnAssign):
                    targets = [statement.target]
                else:
                    return False
                return any(target_binds_metadata(target) for target in targets)

            metadata_assignments = [
                statement
                for statement in module.body
                if is_metadata_assignment(statement)
            ]
            if len(metadata_assignments) != 1:
                raise BundleTransitionError("expected one canonical READY_METADATA assignment")
            assignment = metadata_assignments[0]
            if not (
                isinstance(assignment, ast.Assign)
                and len(assignment.targets) == 1
                and isinstance(assignment.targets[0], ast.Name)
                and assignment.targets[0].id == "READY_METADATA"
            ):
                raise BundleTransitionError(
                    "READY_METADATA must use one unannotated assignment target"
                )
            call = assignment.value
            if not (
                isinstance(call, ast.Call)
                and not call.args
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "build"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "ReadyMetadata"
            ):
                raise BundleTransitionError(
                    "READY_METADATA must be a named-field ReadyMetadata.build call"
                )
            values: dict[str, Any] = {}
            metadata_fields: dict[str, str] = {}
            seen_fields: set[str] = set()
            for keyword in call.keywords:
                if keyword.arg is None or keyword.arg in seen_fields:
                    raise BundleTransitionError("READY_METADATA must use unique named fields")
                seen_fields.add(keyword.arg)
                if keyword.arg in {"source_bundle", "provenance", "operation"}:
                    try:
                        values[keyword.arg] = ast.literal_eval(keyword.value)
                    except (ValueError, TypeError, SyntaxError) as exc:
                        raise BundleTransitionError(
                            f"READY_METADATA {keyword.arg!r} must be a literal"
                        ) from exc
                else:
                    metadata_fields[keyword.arg] = ast.dump(
                        keyword.value,
                        include_attributes=False,
                    )
            try:
                marker = _validate_v2_marker(values["source_bundle"])
            except (KeyError, WorkflowBundleError) as exc:
                raise BundleTransitionError("READY_METADATA has no valid v2 source marker") from exc
            if marker != expected_marker:
                raise BundleTransitionError("READY_METADATA source marker does not match the bundle")
            expected_operation = bundle.provenance.get("operation")
            provenance = values.get("provenance")
            if not isinstance(provenance, Mapping) or provenance.get("operation") != expected_operation:
                raise BundleTransitionError("READY_METADATA provenance does not match the bundle")
            if "operation" in values and values["operation"] != expected_operation:
                raise BundleTransitionError("READY_METADATA operation does not match the bundle")

            # The supported canonical renderers may order metadata keywords
            # differently, so compare non-custody fields by their AST values.
            # Keep every byte outside this single assignment exact. In
            # particular, a second statement after a semicolon on the same
            # line remains in the comparison and cannot be silently dropped.
            line_offsets = [0]
            for line in source.splitlines(keepends=True):
                line_offsets.append(line_offsets[-1] + len(line))

            def byte_offset(line: int, column: int) -> int:
                return line_offsets[line - 1] + column

            start = byte_offset(assignment.lineno, assignment.col_offset)
            end = byte_offset(assignment.end_lineno, assignment.end_col_offset)
            normalized = source[:start] + b"__VIBECOMFY_READY_METADATA__" + source[end:]
            return metadata_fields, normalized

        actual_normalized = normalized_source(actual)
        if actual_normalized == normalized_source(scratchpad):
            return True

        from vibecomfy.porting.convert import _ready_requirements
        from vibecomfy.porting.emit.emit_ready import emit_ready_template_python

        metadata = workflow.metadata
        ready_source = emit_ready_template_python(
            workflow,
            ready_metadata=metadata,
            ready_requirements=_ready_requirements(workflow),
            template_id=str(metadata.get("ready_template") or workflow.id),
            registered_inputs={
                str(name): (str(item.node_id), str(item.field))
                for name, item in workflow.inputs.items()
            },
            external_custody=True,
        ).encode("utf-8")
        return actual_normalized == normalized_source(ready_source)
    except Exception:
        # This check is a safety gate before an IR-based rewrite. Any inability
        # to prove source equivalence must preserve the user's bytes.
        return False


def _read_member(path: Path) -> tuple[bytes | None, str | None]:
    if path.is_symlink():
        raise BundleTransitionError(f"workflow bundle member is a symbolic link: {path}")
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        raise BundleTransitionError(f"could not read workflow bundle member {path}: {exc}") from exc
    return payload, _digest_bytes(payload)


def _member_snapshot(paths: Sequence[Path]) -> tuple[dict[Path, bytes | None], dict[Path, str | None]]:
    payloads: dict[Path, bytes | None] = {}
    digests: dict[Path, str | None] = {}
    for path in paths:
        payload, digest = _read_member(path)
        payloads[path] = payload
        digests[path] = digest
    return payloads, digests


def _assert_snapshot_unchanged(snapshot: Mapping[Path, str | None]) -> None:
    for path, expected in snapshot.items():
        _payload, actual = _read_member(path)
        if actual != expected:
            raise BundleTransitionError(
                f"workflow bundle changed while it was being loaded: {path}; reload it and retry"
            )


def _verified_report_parent(
    python_path: Path,
    *,
    workflow_identity: str,
    sidecar_digest: str | None,
    source_digest: str | None,
) -> Mapping[str, Any] | None:
    """Read a prior local transition receipt only when its stable members match.

    Directly edited Python no longer matches its old member digest, but the
    untouched companion and source archive can still bind the adjacent report
    to the pre-capture bundle. Legacy bundles without a report remain an
    explicitly unknown baseline.
    """
    report_path = python_path.parent / "edit-report.json"
    if report_path.is_symlink():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(report, Mapping):
        return None
    after = report.get("after")
    members = after.get("members") if isinstance(after, Mapping) else None
    if not isinstance(members, Mapping):
        members = report.get("members")
    if not isinstance(members, Mapping):
        return None
    identity = report.get("workflow_identity", report.get("workflow_id"))
    revision = report.get("revision_id", report.get("revision"))
    if identity != workflow_identity or not isinstance(revision, str) or not revision:
        return None
    if members.get("workflow.vibe.json") != ("sha256:" + sidecar_digest if sidecar_digest else None):
        return None
    if source_digest is not None and members.get("source.json") != "sha256:" + source_digest:
        return None
    if source_digest is None and members.get("source.json") is not None:
        return None
    if isinstance(after, Mapping) and after.get("revision_id") not in {None, revision}:
        return None
    return report


def _resolve_output_path(output: str | Path | None, input_python: Path) -> tuple[Path, bool]:
    if output is None:
        return input_python, True
    requested = Path(output).expanduser()
    if requested.exists() and requested.is_dir():
        resolved = requested.resolve() / "workflow.py"
    elif requested.suffix.lower() == ".py":
        resolved = requested.resolve()
    else:
        resolved = requested.resolve() / "workflow.py"
    return resolved, resolved == input_python.resolve()


def _add_parent_evidence(workflow: VibeWorkflow, parent_revision: str) -> None:
    if not parent_revision:
        return
    metadata = dict(getattr(workflow, "metadata", {}) or {})
    existing = metadata.get("revision_evidence", [])
    if isinstance(existing, Mapping):
        records = [dict(value) for value in existing.values() if isinstance(value, Mapping)]
    elif isinstance(existing, (list, tuple)):
        records = [dict(value) for value in existing if isinstance(value, Mapping)]
    else:
        raise BundleTransitionError("workflow revision_evidence is malformed")
    parent_record = {"revision_id": parent_revision, "workflow_identity": workflow.id}
    if parent_record not in records:
        records.append(parent_record)
    metadata["revision_evidence"] = records
    workflow.metadata = metadata


def _manual_capture_input(
    python_path: Path,
) -> tuple[VibeWorkflow, Mapping[str, Any] | None, Mapping[str, Any]]:
    """Load direct source edits under user confirmation and preserve identity.

    An old presentation can become invalid after direct Python node edits.
    In that explicit capture case, retain it only if it still validates; if it
    does not, the new pair starts with an empty presentation while carrying a
    freshly generated custody record for the captured canonical graph.
    """
    from vibecomfy.scratchpad_loader import load_scratchpad

    sidecar_path = _sidecar_path(python_path)
    sidecar_bytes, _digest = _read_member(sidecar_path)
    old_sidecar: Mapping[str, Any] | None = None
    if sidecar_bytes is not None:
        try:
            decoded_sidecar = json.loads(sidecar_bytes.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise BundleTransitionError(f"workflow companion is not valid JSON: {exc}") from exc
        if not isinstance(decoded_sidecar, Mapping):
            raise BundleTransitionError("workflow companion must contain a JSON object")
        if decoded_sidecar.get("format_version") not in {1, 2}:
            raise BundleTransitionError(
                "capture supports generated VibeComfy v1/v2 workflow bundles only"
            )
        old_sidecar = decoded_sidecar

    # The active GateContext owns prompting and the explicit --yes audit path.
    # USER_CONFIRMED would preconfirm external code and silently skip that gate.
    workflow = load_scratchpad(python_path)
    bind = old_sidecar.get("bind") if old_sidecar is not None else None
    # The generated loader validates the source marker and uses it to recover
    # custody metadata, then normalizes it out of workflow.metadata. The
    # companion's bind record remains the stable identity check after load.
    if old_sidecar is not None and not isinstance(bind, Mapping):
        raise BundleTransitionError("capture requires a companion identity marker")
    if isinstance(bind, Mapping) and bind.get("workflow_identity") != workflow.id:
        raise BundleTransitionError(
            "captured Python workflow identity differs from its sibling companion"
        )

    candidate: Mapping[str, Any] | None
    if old_sidecar is None:
        candidate = None
    else:
        try:
            candidate = validate_sidecar(old_sidecar, workflow)
        except WorkflowBundleError:
            if old_sidecar.get("format_version") != 1:
                # Explicit capture authorizes replacing stale presentation,
                # not changing source identity or bypassing Python's trust
                # boundary.
                candidate = None
            else:
                try:
                    candidate = _migrate_legacy_sidecar(old_sidecar, workflow)
                except WorkflowBundleError as exc:
                    raise BundleTransitionError(
                        f"legacy companion cannot be migrated safely: {exc}"
                    ) from exc
    source_provenance = getattr(getattr(workflow, "source", None), "provenance", {})
    clean_provenance = dict(source_provenance) if isinstance(source_provenance, Mapping) else {}
    clean_provenance["operation"] = "captured"
    # The in-place Python bytes already contain the manual changes, so their
    # pre-edit revision cannot be derived from the stale companion. Start an
    # explicit capture baseline instead of claiming an unproven parent.
    clean_provenance.pop("parent_revision", None)
    metadata = dict(workflow.metadata)
    metadata.pop("revision_evidence", None)
    workflow.metadata = metadata
    if candidate is None:
        candidate = _build_v2_sidecar(
            workflow,
            None,
            provenance=clean_provenance,
            operation="captured",
            parent_revision="",
        )
    return workflow, candidate, clean_provenance


def _local_python_path(reference: str | Path) -> Path:
    resolved, python_path, _operation = _resolve_reference(reference)
    if python_path is None or Path(python_path).suffix.lower() != ".py":
        raise BundleTransitionError("workflow capture needs a local generated Python bundle")
    raw_path = Path(python_path).expanduser()
    if raw_path.is_symlink():
        raise BundleTransitionError(f"workflow Python source is a symbolic link: {raw_path}")
    path = raw_path.resolve()
    if not path.is_file():
        raise BundleTransitionError(f"workflow Python source does not exist: {path}")
    return path


def _ui_capture_input(
    bundle: WorkflowBundle,
    graph: Mapping[str, Any],
    *,
    schema_provider: Any,
) -> tuple[VibeWorkflow, Mapping[str, Any], Mapping[str, Any], tuple[Mapping[str, Any], ...]]:
    """Import an explicitly submitted UI graph against the bound workflow ID."""
    from vibecomfy.ingest.normalize import _named_import, door_import_source_kind
    from vibecomfy.porting.edit._diff import diff

    source_kind = door_import_source_kind(graph)
    explicit = any(key in graph for key in ("workflow_id", "workflow_identity"))
    # ComfyUI canvas documents use top-level `id` for the canvas document,
    # not for the VibeComfy workflow. The single import-shape classifier has
    # already identified those as UI, so API/envelope `id` can bind identity.
    if source_kind != "ui" and "id" in graph:
        explicit = True
    source_identity = graph.get("source")
    if isinstance(source_identity, Mapping) and any(
        key in source_identity for key in ("id", "workflow_identity", "workflow_id")
    ):
        explicit = True
    # A UI/API export commonly carries no workflow-level identity. The caller
    # supplied the canonical bundle path, so bind that projection to its
    # already-known identity. Any identity it does declare remains binding.
    workflow_id = (
        _import_identity(graph, source_kind=source_kind)
        if explicit
        else bundle.workflow.id
    )
    if workflow_id != bundle.workflow.id:
        raise BundleTransitionError(
            "captured UI workflow identity differs from the bound canonical workflow"
        )
    payload = _split_import_api(graph) if source_kind == "api" else dict(graph)
    payload.pop("workflow_id", None)
    payload.pop("workflow_identity", None)
    payload.pop("id", None)
    workflow = _named_import(
        payload,
        source_path=str(bundle.python_path),
        workflow_id=workflow_id,
        schema_provider=schema_provider,
    )
    if workflow.id != bundle.workflow.id:
        raise BundleTransitionError("captured UI graph changed canonical workflow identity")
    _add_parent_evidence(workflow, bundle.revision_id)
    provenance = dict(bundle.provenance)
    provenance["operation"] = "captured"
    delta = tuple(_jsonable(item) for item in diff(bundle.workflow, workflow))
    return workflow, graph, provenance, delta


def _schema_provider_with_uid_aliases(
    provider: Any,
    workflow: VibeWorkflow,
    *,
    tool_calls: Sequence[Mapping[str, Any]] = (),
) -> Any:
    """Freeze the edit catalog and bind classes to canonical UIDs.

    UI ingress schema snapshots key node classes by numeric canvas IDs, while
    typed tools correctly target stable canonical UIDs. Add that proven
    identity correspondence to a detached snapshot. The normal offline
    authoring provider is a live catalog and does not itself expose a
    ``SchemaSnapshot``; freeze exactly the classes in the current workflow
    and any explicitly added by this operation once at the transition
    boundary so all subsequent edit work is snapshot-only.
    """
    from vibecomfy.schema import (
        FrozenSchemaSnapshotProvider,
        schema_for,
    )
    from vibecomfy.schema.types import (
        capture_schema_snapshot,
        schema_payload_from_node_schema,
        schema_snapshot_to_payload,
    )

    snapshot = getattr(provider, "snapshot", None)
    from vibecomfy.schema.types import SchemaSnapshot

    generated_snapshot = not isinstance(snapshot, SchemaSnapshot)
    try:
        from vibecomfy.identity.uid import make_uid
        from vibecomfy.porting.edit._ir_utils import build_recursive_edit_index

        recursive_index = build_recursive_edit_index(workflow)
        requested = set()
        identity_classes: dict[str, set[str]] = {}
        scoped_node_classes: dict[str, str] = {}
        for scope_path, scope in recursive_index.scopes.items():
            for ref in scope.nodes.values():
                node = ref.node
                class_type = (
                    getattr(node, "class_type", None)
                    if not isinstance(node, Mapping)
                    else node.get("type", node.get("class_type"))
                )
                if not isinstance(class_type, str) or not class_type:
                    continue
                requested.add(class_type)
                for identity in {str(ref.uid), str(ref.node_id)}:
                    scoped_node_classes[make_uid(scope_path, identity)] = class_type
                    identity_classes.setdefault(identity, set()).add(class_type)
        ambiguous_local_identities = {
            identity for identity, class_types in identity_classes.items()
            if len(class_types) > 1
        }
        # Existing edit admission resolves ordinary node references through
        # local UIDs. Keep those aliases only when they identify one class
        # across the full recursive workflow; scoped keys preserve exact
        # identity for future scope-aware consumers and avoid lossy overwrite.
        for identity, class_types in identity_classes.items():
            if len(class_types) == 1:
                scoped_node_classes[identity] = next(iter(class_types))
    except Exception as exc:
        raise BundleTransitionError(
            "could not index recursive workflow schemas for editing: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(snapshot, SchemaSnapshot):
        # CLI authoring providers intentionally expose schemas without a
        # snapshot. Query only classes that this operation can touch, then
        # freeze those results rather than making callers configure a second
        # provider or allowing the edit session to consult ambient schemas.
        try:
            def include_added_class(tool: str, args: Any) -> None:
                if tool == "add_node" and isinstance(args, Mapping):
                    class_type = args.get("class_type")
                    if isinstance(class_type, str) and class_type:
                        requested.add(class_type)
                elif tool == "edit_batch" and isinstance(args, Mapping):
                    ops = args.get("ops")
                    if isinstance(ops, list):
                        for item in ops:
                            if isinstance(item, Mapping) and isinstance(item.get("op"), str):
                                include_added_class(
                                    str(item["op"]),
                                    {key: value for key, value in item.items() if key != "op"},
                                )

            for call in tool_calls:
                if isinstance(call, Mapping) and isinstance(call.get("tool"), str):
                    include_added_class(str(call["tool"]), call.get("args"))

            raw_schemas: dict[str, Any] = {}
            for class_type in sorted(requested):
                schema = schema_for(provider, class_type)
                if schema is not None:
                    raw_schemas[class_type] = schema_payload_from_node_schema(
                        class_type, schema
                    )
            missing = sorted(requested - set(raw_schemas))
            frozen = capture_schema_snapshot(
                class_types=tuple(sorted(requested)),
                request_snapshot={
                    "schemas": raw_schemas,
                    "missing_classes": missing,
                },
                node_classes=scoped_node_classes,
            )
            snapshot = frozen
        except Exception as exc:
            raise BundleTransitionError(
                "could not freeze the available node schemas for workflow editing: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
    node_classes = dict(snapshot.node_classes)
    node_classes.update(scoped_node_classes)
    for identity in ambiguous_local_identities:
        node_classes.pop(identity, None)
    if not generated_snapshot and all(
        snapshot.node_classes.get(key) == value for key, value in node_classes.items()
    ) and not ambiguous_local_identities:
        return provider
    payload = schema_snapshot_to_payload(snapshot)
    payload.pop("content_digest", None)
    payload.pop("contract_version", None)
    aliased = capture_schema_snapshot(
        class_types=tuple(snapshot.schemas),
        request_snapshot=payload,
        node_classes=node_classes,
    )
    return FrozenSchemaSnapshotProvider(aliased)


def _typed_operations(
    session: Any,
    tool_calls: Sequence[Mapping[str, Any]],
) -> tuple[Any, ...]:
    from vibecomfy.porting.edit.typed_tools import lower_edit_tool_call

    calls = tuple(tool_calls)
    if not calls:
        raise BundleTransitionError("an edit needs at least one typed tool call")
    normalized: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        if not isinstance(call, Mapping) or not isinstance(call.get("tool"), str):
            raise BundleTransitionError(f"tool_calls[{index}] requires a string tool name")
        args = call.get("args")
        if not isinstance(args, Mapping):
            raise BundleTransitionError(f"tool_calls[{index}].args must be an object")
        normalized.append({"op": call["tool"], **dict(args)})
    if len(normalized) == 1 and normalized[0]["op"] == "edit_batch":
        item = normalized[0]
        return lower_edit_tool_call(
            session,
            "edit_batch",
            {key: value for key, value in item.items() if key != "op"},
        )
    if len(normalized) == 1:
        item = normalized[0]
        return lower_edit_tool_call(session, item["op"], {key: value for key, value in item.items() if key != "op"})
    if any(item["op"] == "edit_batch" for item in normalized):
        raise BundleTransitionError("edit_batch cannot be nested within tool_calls")
    return lower_edit_tool_call(session, "edit_batch", {"ops": normalized})


def transition_bundle(
    reference: str | Path,
    *,
    tool_calls: Sequence[Mapping[str, Any]] = (),
    capture: bool = False,
    candidate_python: str | Path | None = None,
    capture_graph: Mapping[str, Any] | None = None,
    expected_parent_revision: str | None = None,
    output: str | Path | None = None,
    dry_run: bool = False,
    schema_provider: Any = None,
) -> BundleTransitionResult:
    """Apply one typed edit batch or explicitly capture a workflow snapshot.

    Local edits replace the loaded pair in place by default. ``output`` may
    name a Python file or a bundle directory; a separate destination receives
    an exact copy of sibling ``source.json`` when the input has one. Captures
    execute the user-edited generated Python through the normal confirmation
    boundary and verify its identity against the existing companion.
    """
    if capture and capture_graph is not None:
        raise BundleTransitionError("choose direct-Python capture or UI-graph capture")
    if candidate_python is not None and not capture:
        raise BundleTransitionError("candidate_python is only valid for direct-Python capture")
    if candidate_python is not None and capture_graph is not None:
        raise BundleTransitionError("choose a Python candidate or UI-graph capture")
    if capture and tool_calls:
        raise BundleTransitionError("capture and typed edit operations cannot be combined")
    if capture_graph is not None and tool_calls:
        raise BundleTransitionError("capture and typed edit operations cannot be combined")
    if not capture and capture_graph is None and not tool_calls:
        raise BundleTransitionError("provide typed edit operations or use explicit capture")

    from vibecomfy.schema import get_authoring_schema_provider

    schema = schema_provider or get_authoring_schema_provider(on_demand_schemas=False)
    direct_capture = capture
    candidate_path = _local_python_path(candidate_python) if candidate_python is not None else None
    ui_capture = capture_graph is not None
    source_path = _local_python_path(reference)
    source_archive = source_path.parent / "source.json"
    member_paths = (source_path, _sidecar_path(source_path), source_archive)
    payloads, expected_input = _member_snapshot(member_paths)
    initial: WorkflowBundle | None = None
    if direct_capture and candidate_path is None:
        kind = "python_capture"
    else:
        # The active GateContext owns interactive confirmation and --yes audit.
        # USER_CONFIRMED would silently preconfirm external Python here.
        initial = load_bundle(reference, schema_provider=schema)
        initial.require_canonical_authority("workflow editing")
        if initial.python_path is None or initial.python_path.resolve() != source_path:
            raise BundleTransitionError("loaded workflow does not resolve to its local Python source")
        kind = "python_capture" if direct_capture else "ui_capture" if ui_capture else "edit"

    # Confirm that loading saw the bytes hashed before it began; these digests
    # become the compare-and-swap input checked immediately before replacement.
    _assert_snapshot_unchanged(expected_input)
    archived_source = payloads[source_archive]
    has_source_archive = archived_source is not None

    apply_result = None
    semantic_diff: tuple[Mapping[str, Any], ...] | None
    if direct_capture and candidate_path is not None:
        # Astrid and other immutable callers retain the exact admitted parent
        # pair and pass edited Python separately. This keeps the before
        # revision/digests loadable while the existing capture path preserves
        # the candidate's executable source bytes.
        assert initial is not None
        if expected_parent_revision and initial.revision_id != expected_parent_revision:
            raise BundleTransitionError(
                "capture parent revision does not match the admitted parent; refresh the workflow inputs"
            )
        candidate_members = (candidate_path, _sidecar_path(candidate_path))
        candidate_payloads, candidate_snapshot = _member_snapshot(candidate_members)
        _assert_snapshot_unchanged(candidate_snapshot)
        try:
            workflow, candidate_ui, provenance = _manual_capture_input(candidate_path)
        except Exception as exc:
            if isinstance(exc, (BundleTransitionError, CapabilityFenceError)):
                raise
            raise BundleTransitionError(f"could not capture direct Python edit: {exc}") from exc
        if workflow.id != initial.workflow.id:
            raise BundleTransitionError("captured workflow identity differs from the admitted parent")
        parent_revision = initial.revision_id
        parent_evidence = {
            "revision_id": initial.revision_id,
            "workflow_identity": initial.workflow.id,
        }
        _add_parent_evidence(workflow, parent_revision)
        before_semantic = initial.semantic_digest
        before_ui = initial.ui_digest
        operations = ()
        from vibecomfy.porting.edit._diff import diff

        semantic_diff = tuple(_jsonable(item) for item in diff(initial.workflow, workflow))
        diagnostics = ()
        operation = "captured"
        candidate_source = candidate_payloads[candidate_path]
        if candidate_source is None:
            raise BundleTransitionError("capture Python candidate disappeared while it was being loaded")
        preserved_python_source = (
            candidate_source if _has_v2_source_marker(candidate_source) else None
        )
    elif direct_capture:
        try:
            workflow, candidate_ui, provenance = _manual_capture_input(source_path)
        except Exception as exc:
            if isinstance(exc, (BundleTransitionError, CapabilityFenceError)):
                raise
            raise BundleTransitionError(f"could not capture direct Python edit: {exc}") from exc
        marker_bind = candidate_ui.get("bind") if isinstance(candidate_ui, Mapping) else None
        if not isinstance(marker_bind, Mapping) or marker_bind.get("workflow_identity") != workflow.id:
            raise BundleTransitionError("captured workflow identity changed; refusing to publish")
        # A manually edited Python file has no trustworthy pre-edit graph
        # unless its untouched parent bundle is supplied. Report that
        # limitation directly instead of manufacturing a before digest.
        source_digest = expected_input[source_archive] if has_source_archive else None
        prior_report = _verified_report_parent(
            source_path,
            workflow_identity=workflow.id,
            sidecar_digest=expected_input[_sidecar_path(source_path)],
            source_digest=source_digest,
        )
        prior_after = prior_report.get("after") if isinstance(prior_report, Mapping) else None
        parent_revision_value = (
            prior_after.get("revision_id")
            if isinstance(prior_after, Mapping)
            else prior_report.get("revision_id", prior_report.get("revision"))
            if isinstance(prior_report, Mapping)
            else None
        )
        if not parent_revision_value:
            evidence = provenance.get("revision_evidence") if isinstance(provenance, Mapping) else None
            evidence_records = (
                [record for record in evidence if isinstance(record, Mapping)]
                if isinstance(evidence, (list, tuple))
                else [record for record in evidence.values() if isinstance(record, Mapping)]
                if isinstance(evidence, Mapping)
                else []
            )
            bound_records = [
                record for record in evidence_records
                if record.get("workflow_identity", record.get("workflow_id")) == workflow.id
                and isinstance(record.get("revision_id"), str)
                and record.get("revision_id")
            ]
            if bound_records:
                # Generated Python carries the exact revision-evidence chain;
                # its last bound entry is the source bundle from which direct
                # edits were made. No graph operations are inferred from it.
                parent_revision_value = bound_records[-1]["revision_id"]
        parent_revision = str(parent_revision_value) if parent_revision_value else ""
        parent_evidence = (
            {"revision_id": parent_revision, "workflow_identity": workflow.id}
            if parent_revision
            else None
        )
        if parent_revision:
            _add_parent_evidence(workflow, parent_revision)
        before_semantic_value = prior_after.get("semantic_digest") if isinstance(prior_after, Mapping) else None
        before_ui_value = prior_after.get("ui_digest") if isinstance(prior_after, Mapping) else None
        if not before_ui_value and parent_revision:
            try:
                old_sidecar_bytes = payloads[_sidecar_path(source_path)]
                old_sidecar = json.loads(old_sidecar_bytes.decode("utf-8")) if old_sidecar_bytes else None
            except (UnicodeError, json.JSONDecodeError):
                old_sidecar = None
            if isinstance(old_sidecar, Mapping):
                before_ui_value = _sidecar_ui_digest(old_sidecar)
        before_semantic = str(before_semantic_value) if before_semantic_value else None
        before_ui = str(before_ui_value) if before_ui_value else None
        operations: tuple[Mapping[str, Any], ...] = ()
        semantic_diff = None
        diagnostics: tuple[Mapping[str, Any], ...] = (
            ({
                "code": "capture_diff_unavailable",
                "message": "The pre-capture graph is not available, so no individual operations or graph diff are claimed.",
                "severity": "info",
            },)
            if parent_revision
            else ({
                "code": "capture_baseline_unavailable",
                "message": "No trusted pre-capture revision or graph was available; this capture starts a new baseline and claims no before diff or individual operations.",
                "severity": "info",
            },)
        )
        operation = "captured"
        preserved_python_source = (
            payloads[source_path]
            if _has_v2_source_marker(payloads[source_path])
            else None
        )
    elif ui_capture:
        assert initial is not None
        if initial.python_path is None:
            raise BundleTransitionError("UI capture needs a local canonical Python bundle")
        if not _is_canonical_python_source(initial, source_path):
            raise BundleTransitionError(
                "workflow.py differs from the canonical generated source, so a UI capture "
                "cannot safely preserve it; keep the current bundle unchanged and reconcile "
                "the graph in Python first"
            )
        if not isinstance(capture_graph, Mapping):
            raise BundleTransitionError("capture_graph must be a UI graph object")
        try:
            workflow, candidate_ui, provenance, semantic_diff = _ui_capture_input(
                initial, capture_graph, schema_provider=schema
            )
        except Exception as exc:
            if isinstance(exc, BundleTransitionError):
                raise
            raise BundleTransitionError(f"could not capture UI graph: {exc}") from exc
        parent_revision = initial.revision_id
        parent_evidence = {
            "revision_id": initial.revision_id,
            "workflow_identity": initial.workflow.id,
        }
        before_semantic = initial.semantic_digest
        before_ui = initial.ui_digest
        operations = ()
        diagnostics = ()
        operation = "captured"
    else:
        assert initial is not None
        if not _is_canonical_python_source(initial, source_path):
            raise BundleTransitionError(
                "workflow.py differs from the canonical generated source, so a typed edit "
                "cannot safely preserve it; edit it directly and capture it, or restore the "
                "canonical generated source before typed editing"
            )
        if schema is None:
            raise BundleTransitionError("workflow edit needs an authoring schema provider")
        edit_schema = _schema_provider_with_uid_aliases(
            schema, initial.workflow, tool_calls=tool_calls
        )
        raw_ui = initial.materialize_ui(schema_provider=edit_schema, strict=True)
        from vibecomfy.ingest.snapshot import snapshot_of
        from vibecomfy.porting.edit.session import EditSession

        session = EditSession(
            raw_ui,
            initial_workflow=initial.workflow,
            workflow_snapshot=snapshot_of(initial.workflow),
            schema_provider=edit_schema,
            use_ingest_presentation=True,
        )
        try:
            ops = _typed_operations(session, tool_calls)
        except Exception as exc:
            raise BundleTransitionError(str(exc)) from exc
        apply_result = session.apply_ops(ops, expected_revision=0)
        if not apply_result.ok:
            # Keep the ordered evaluator ledger intact when crossing the
            # bundle boundary.  Flattening only ``code: message`` hid the
            # first rejected operation and its endpoint detail behind dozens
            # of downstream topology diagnostics, making a safe correction
            # indistinguishable from a blind retry.
            transition_report = [
                {
                    "occurrence": transition.occurrence,
                    "outcome": transition.outcome,
                    "submitted": _jsonable(transition.submitted),
                    "normalized": _jsonable(transition.normalized),
                    "diagnostics": [_jsonable(item) for item in transition.diagnostics],
                }
                for transition in apply_result.transitions
            ]
            details = json.dumps(
                {
                    "reason": apply_result.reason,
                    "diagnostics": [_jsonable(item) for item in apply_result.diagnostics],
                    "transitions": transition_report,
                },
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            raise BundleTransitionError(details or "workflow edit was rejected")
        if not isinstance(apply_result.workflow, VibeWorkflow) or apply_result.graph is None:
            raise BundleTransitionError("accepted edit did not produce a canonical workflow and presentation")
        workflow = apply_result.workflow
        candidate_ui = apply_result.graph
        parent_revision = initial.revision_id
        parent_evidence = {
            "revision_id": initial.revision_id,
            "workflow_identity": initial.workflow.id,
        }
        _add_parent_evidence(workflow, parent_revision)
        provenance = dict(initial.provenance)
        provenance["operation"] = "authored"
        before_semantic = initial.semantic_digest
        before_ui = initial.ui_digest
        operations = tuple(_jsonable(item) for item in apply_result.landed_ops)
        semantic_diff = operations
        diagnostics = tuple(_jsonable(item) for item in apply_result.diagnostics)
        operation = "authored"

    if not direct_capture:
        preserved_python_source = None

    destination, in_place = _resolve_output_path(output, source_path)
    if in_place:
        # Local materialization may replace only the exact pair (and preserve
        # the original archive). The publisher rechecks these digests directly
        # before its first visible replacement.
        expected_publish = {
            source_path: expected_input[source_path],
            _sidecar_path(source_path): expected_input[_sidecar_path(source_path)],
        }
        if has_source_archive:
            expected_publish[source_archive] = expected_input[source_archive]
        extra_members: dict[Path, bytes] = {}
    else:
        output_archive = destination.parent / "source.json"
        if output_archive == source_archive:
            raise BundleTransitionError(
                "--out must name a separate bundle directory when the input has source.json"
            )
        expected_publish = {
            destination: None,
            _sidecar_path(destination): None,
        }
        extra_members = {}
        if has_source_archive:
            expected_publish[output_archive] = None
            extra_members[output_archive] = archived_source
        # Recheck the input bundle and archived evidence before publishing an
        # independent copy too; output publication must reflect one source
        # revision, not bytes observed at different times.
        expected_publish.update({
            source_path: expected_input[source_path],
            _sidecar_path(source_path): expected_input[_sidecar_path(source_path)],
            **({source_archive: expected_input[source_archive]} if has_source_archive else {}),
        })

    if dry_run:
        with tempfile.TemporaryDirectory(prefix="vibecomfy-edit-preview-") as temporary:
            preview_path = Path(temporary) / destination.name
            preview_members = {
                preview_path: None,
                _sidecar_path(preview_path): None,
            }
            preview_extras: dict[Path, bytes] = {}
            if has_source_archive:
                preview_archive = preview_path.parent / "source.json"
                preview_members[preview_archive] = None
                preview_extras[preview_archive] = archived_source
            result_bundle = emit_bundle_with_candidate(
                workflow,
                preview_path,
                provenance,
                candidate_ui,
                parent_revision=parent_revision,
                parent_evidence=parent_evidence,
                operation=operation,
                expected_members=preview_members,
                extra_members=preview_extras,
                preserved_python_source=preserved_python_source,
            )
        status = "preview"
    else:
        if direct_capture and candidate_path is not None:
            _assert_snapshot_unchanged(candidate_snapshot)
        result_bundle = emit_bundle_with_candidate(
            workflow,
            destination,
            provenance,
            candidate_ui,
            parent_revision=parent_revision,
            parent_evidence=parent_evidence,
            operation=operation,
            expected_members=expected_publish,
            extra_members=extra_members,
            preserved_python_source=preserved_python_source,
        )
        # The publisher already validated the staged generated Python before
        # replacement. This trusted reload is a read-back assertion over the
        # bytes produced by that publisher, not approval of external source.
        from vibecomfy.security.provenance import Provenance

        reloaded = load_bundle(
            destination,
            trust=Provenance.USER_CONFIRMED,
            schema_provider=schema,
        )
        if reloaded.revision_id != result_bundle.revision_id:
            raise BundleTransitionError(
                "published bundle did not reload to the same canonical revision"
            )
        status = "saved"

    return BundleTransitionResult(
        status=status,
        kind=kind,
        input_path=str(source_path),
        python_path=str(destination),
        companion_path=str(_sidecar_path(destination)),
        source_archive_path=str(destination.parent / "source.json") if has_source_archive else None,
        parent_revision=parent_revision or None,
        revision_id=result_bundle.revision_id,
        before_semantic_digest=before_semantic,
        semantic_digest=result_bundle.semantic_digest,
        before_ui_digest=before_ui,
        ui_digest=result_bundle.ui_digest,
        operations=operations,
        diff=semantic_diff,
        diagnostics=diagnostics,
    )


__all__ = ["BundleTransitionError", "BundleTransitionResult", "transition_bundle"]
