"""Final live-schema reconciliation immediately before an executable queue."""

from __future__ import annotations

import copy
import hashlib
import inspect
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.porting.widgets.historical import (
    HistoricalWidgetMappingRefused,
    HistoricalWidgetReconciliation,
    admit_historical_widget_mappings,
)
from vibecomfy.workflow import RawWidgetPayload, VibeWorkflow
from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
    WorkflowBundle,
    _atomic_publish_pair,
    _build_v2_sidecar,
    _generated_metadata_expressions,
    _make_bundle,
    _sidecar_ui_digest,
    _sidecar_path,
    _v2_marker,
    canonical_digest,
)


class ReconciliationError(RuntimeError):
    """A live schema could not safely reconcile the executable IR."""

    def __init__(self, message: str, *, diagnostics: list[dict[str, Any]] | None = None) -> None:
        self.diagnostics = list(diagnostics or [])
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    bundle: WorkflowBundle
    changed: bool
    schema: dict[str, Any]
    decisions: tuple[dict[str, Any], ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    """Immutable identity of the reconciled projection used for queueing."""

    source_revision: str
    workflow_semantic_digest: str
    api_digest: str
    schema_digest: str | None
    schema_generation: str | None
    final_sinks: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_revision": self.source_revision,
            "workflow_semantic_digest": self.workflow_semantic_digest,
            "api_digest": self.api_digest,
            "schema_digest": self.schema_digest,
            "schema_generation": self.schema_generation,
            "final_sinks": [copy.deepcopy(item) for item in self.final_sinks],
        }


def build_execution_snapshot(
    bundle: WorkflowBundle,
    record: ApprovedProjectionRecord,
    *,
    schema: Mapping[str, Any] | None = None,
) -> ExecutionSnapshot:
    """Capture one source/compiled/schema identity for all later runtime gates."""
    if not isinstance(bundle, WorkflowBundle) or not isinstance(record, ApprovedProjectionRecord):
        raise TypeError("execution snapshots require an approved workflow bundle and record")
    return ExecutionSnapshot(
        source_revision=str(bundle.revision_id),
        workflow_semantic_digest=str(bundle.semantic_digest),
        api_digest=str(record.api_digest),
        schema_digest=(str(schema.get("digest")) if isinstance(schema, Mapping) and schema.get("digest") else None),
        schema_generation=(str(schema.get("generation")) if isinstance(schema, Mapping) and schema.get("generation") else None),
        final_sinks=tuple({
            "node_id": str(getattr(output, "node_id", "")),
            "output_type": str(getattr(output, "output_type", "") or ""),
            "name": getattr(output, "name", None),
        } for output in bundle.workflow.outputs),
    )


def assert_execution_snapshot(
    snapshot: Mapping[str, Any],
    bundle: WorkflowBundle,
    record: ApprovedProjectionRecord,
    *,
    schema_provider: Any | None = None,
    schema_generation: str | int | None = None,
) -> None:
    """Reject any mutation between reconciliation and transport."""
    current_schema: dict[str, Any] | None = None
    if schema_provider is not None:
        raw_object_info = getattr(schema_provider, "_object_info", None)
        if isinstance(raw_object_info, Mapping):
            from vibecomfy.schema.cache import object_info_payload_checksum

            digest = getattr(schema_provider, "_object_info_digest", None)
            digest = str(digest) if digest else object_info_payload_checksum(dict(raw_object_info))
            server = str(
                getattr(schema_provider, "_active_server_url", None)
                or getattr(schema_provider, "server_url", None)
                or "target"
            )
            generation = schema_generation if schema_generation is not None else getattr(schema_provider, "generation", None)
            current_schema = {
                "digest": digest,
                "generation": str(generation) if generation is not None else f"live:{server}:{digest}",
            }
    current = build_execution_snapshot(bundle, record, schema=current_schema)
    expected = {
        "source_revision": str(snapshot.get("source_revision")),
        "workflow_semantic_digest": str(snapshot.get("workflow_semantic_digest")),
        "api_digest": str(snapshot.get("api_digest")),
    }
    actual = {
        "source_revision": current.source_revision,
        "workflow_semantic_digest": current.workflow_semantic_digest,
        "api_digest": current.api_digest,
    }
    expected_schema = {
        "schema_digest": snapshot.get("schema_digest"),
        "schema_generation": snapshot.get("schema_generation"),
    }
    actual_schema = {
        "schema_digest": current.schema_digest,
        "schema_generation": current.schema_generation,
    }
    schema_changed = any(
        value is not None and actual_schema[key] != value
        for key, value in expected_schema.items()
    )
    if actual != expected or schema_changed:
        raise ReconciliationError(
            "execution snapshot changed after final reconciliation",
            diagnostics=[{
                "code": "execution_snapshot_changed",
                "expected": expected,
                "actual": actual,
                "expected_schema": expected_schema,
                "actual_schema": actual_schema,
            }],
        )


def _live_schema_identity(provider: Any) -> tuple[str, str, dict[str, Any]]:
    try:
        refresh = getattr(provider, "refresh", None)
        object_info = refresh() if callable(refresh) else provider.object_info()
    except Exception as exc:
        raise ReconciliationError(f"live /object_info query failed: {exc}") from exc
    if not isinstance(object_info, Mapping):
        raise ReconciliationError("live /object_info response was not an object")
    return _schema_identity_from_payload(provider, object_info)


def _schema_identity_from_payload(
    provider: Any, object_info: Mapping[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    from vibecomfy.schema.cache import object_info_payload_checksum

    digest = object_info_payload_checksum(dict(object_info))
    server = str(getattr(provider, "_active_server_url", None) or getattr(provider, "server_url", "target"))
    generation = str(getattr(provider, "generation", None) or f"live:{server}:{digest}")
    return digest, generation, {
        "status": "captured",
        "server_url": server,
        "digest": digest,
        "generation": generation,
        "node_count": len(object_info),
    }


async def reconcile_before_queue_async(
    bundle: WorkflowBundle,
    *,
    target_schema_provider: Any,
    target_schema_generation: str | int | None = None,
    publish: bool = True,
) -> ReconciliationResult:
    """Async entry point for runtimes whose live schema query is awaitable."""
    try:
        cached_object_info = getattr(target_schema_provider, "_object_info", None)
        requires_fresh_target = bool(getattr(target_schema_provider, "requires_fresh_target", False))
        if isinstance(cached_object_info, Mapping) and not requires_fresh_target:
            object_info = cached_object_info
        else:
            object_info_async = getattr(target_schema_provider, "object_info_async", None)
            if callable(object_info_async):
                object_info = object_info_async()
                if inspect.isawaitable(object_info):
                    object_info = await object_info
            else:
                refresh = getattr(target_schema_provider, "refresh", None)
                object_info = refresh() if callable(refresh) else target_schema_provider.object_info()
                if inspect.isawaitable(object_info):
                    object_info = await object_info
    except Exception as exc:
        raise ReconciliationError(f"live /object_info query failed: {exc}") from exc
    if not isinstance(object_info, Mapping):
        raise ReconciliationError("live /object_info response was not an object")
    digest, generation, schema = _schema_identity_from_payload(target_schema_provider, object_info)
    if target_schema_generation is not None:
        generation = str(target_schema_generation)
        schema = {**schema, "generation": generation}
    return reconcile_before_queue(
        bundle,
        target_schema_provider=target_schema_provider,
        target_schema_generation=generation,
        publish=publish,
        _captured_identity=(digest, generation, schema),
    )


def _widget_values(node: Any) -> list[Any]:
    raw = getattr(node, "raw_widgets", None)
    values = getattr(raw, "values", None)
    if isinstance(values, (list, tuple)):
        return copy.deepcopy(list(values))
    indexed: list[tuple[int, Any]] = []
    for store_name in ("widgets", "inputs"):
        store = getattr(node, store_name, {})
        if not isinstance(store, Mapping):
            continue
        for key, value in store.items():
            text = str(key)
            if text.startswith("widget_"):
                try:
                    indexed.append((int(text.split("_", 1)[1]), copy.deepcopy(value)))
                except ValueError:
                    continue
    return [value for _index, value in sorted(indexed)]


def _mapping_conflicts(
    workflow: VibeWorkflow,
    node_id: str,
    decision: HistoricalWidgetReconciliation,
) -> list[dict[str, Any]]:
    node = workflow.nodes.get(str(node_id))
    if node is None:
        return []
    diagnostics: list[dict[str, Any]] = []
    targets: dict[str, Any] = {}
    for mapping in decision.mappings:
        prior = targets.get(mapping.target_field, object())
        if mapping.target_field in targets and prior != mapping.source_value:
            diagnostics.append({
                "code": "ambiguous_widget_mapping_conflict",
                "node_id": str(node_id),
                "class_type": str(node.class_type),
                "source_span": mapping.source_span,
                "source_field": mapping.source_field,
                "target_field": mapping.target_field,
                "source_value": copy.deepcopy(mapping.source_value),
                "conflicting_value": copy.deepcopy(prior),
                "repair_options": [
                    "edit the Python input explicitly",
                    "refresh the retained source widget roster",
                ],
            })
        targets[mapping.target_field] = copy.deepcopy(mapping.source_value)
        for store_name in ("widgets", "inputs"):
            store = getattr(node, store_name, {})
            if not isinstance(store, Mapping) or mapping.target_field not in store:
                continue
            current = store[mapping.target_field]
            if current != mapping.source_value:
                diagnostics.append({
                    "code": "ambiguous_widget_mapping_conflict",
                    "node_id": str(node_id),
                    "class_type": str(node.class_type),
                    "source_span": mapping.source_span,
                    "source_field": mapping.source_field,
                    "target_field": mapping.target_field,
                    "source_value": copy.deepcopy(mapping.source_value),
                    "conflicting_value": copy.deepcopy(current),
                    "repair_options": [
                        "edit the Python input explicitly",
                        "remove the conflicting semantic input before reconciliation",
                    ],
                })
        if any(
            str(edge.to_node) == str(node_id)
            and str(edge.to_input) == mapping.target_field
            for edge in workflow.edges
        ):
            diagnostics.append({
                "code": "ambiguous_widget_mapping_conflict",
                "node_id": str(node_id),
                "class_type": str(node.class_type),
                "source_span": mapping.source_span,
                "source_field": mapping.source_field,
                "target_field": mapping.target_field,
                "source_value": copy.deepcopy(mapping.source_value),
                "conflicting_value": "authored link",
                "repair_options": [
                    "keep the authored link and remove the legacy literal",
                    "edit the Python input explicitly",
                ],
            })
    return diagnostics


def _apply_mapping(workflow: VibeWorkflow, node_id: str, decision: HistoricalWidgetReconciliation) -> bool:
    node = workflow.nodes.get(str(node_id))
    if node is None:
        return False
    changed = False
    by_source_index = {item.source_widget_index: item for item in decision.mappings}
    for index, mapping in by_source_index.items():
        source_key = f"widget_{index}"
        for store_name in ("widgets", "inputs"):
            store = getattr(node, store_name, None)
            if not isinstance(store, dict):
                continue
            if source_key in store:
                value = store.pop(source_key)
                if store.get(mapping.target_field) != value:
                    store[mapping.target_field] = copy.deepcopy(value)
                    changed = True
        for edge in workflow.edges:
            if str(edge.to_node) == str(node_id) and str(edge.to_input) == source_key:
                edge.to_input = mapping.target_field
                changed = True
    raw = getattr(node, "raw_widgets", None)
    values = getattr(raw, "values", None)
    if isinstance(values, (list, tuple)):
        updated = list(values)
        for mapping in decision.mappings:
            if mapping.target_widget_index >= len(updated):
                updated.extend([None] * (mapping.target_widget_index + 1 - len(updated)))
            if updated[mapping.target_widget_index] != mapping.source_value:
                updated[mapping.target_widget_index] = copy.deepcopy(mapping.source_value)
                changed = True
        node.raw_widgets = replace(raw, values=updated, length=len(updated))
    node.metadata.setdefault("reconciliation", {})
    node.metadata["reconciliation"] = {
        "status": decision.status,
        "source_revision": decision.source_revision,
        "target_schema_digest": decision.target_schema_digest,
        "target_schema_generation": decision.target_schema_generation,
        "mappings": [item.to_dict() for item in decision.mappings],
        "preserved_slots": [item.to_dict() for item in decision.preserved_slots],
    }
    return changed


def _presentation_candidate(bundle: WorkflowBundle) -> dict[str, Any] | None:
    sidecar = bundle.ui_sidecar
    if not isinstance(sidecar, Mapping):
        return None
    if sidecar.get("format_version") == 2:
        presentation = sidecar.get("presentation")
        if not isinstance(presentation, Mapping):
            return None
        return {
            "format_version": 1,
            "bind": {
                "workflow_identity": bundle.workflow.id,
                "semantic_digest": bundle.semantic_digest,
            },
            **{key: copy.deepcopy(presentation.get(key, default)) for key, default in (
                ("nodes", {}), ("links", []), ("groups", []), ("canvas", {}), ("annotations", []),
            )},
        }
    return copy.deepcopy(dict(sidecar))


def _materialize_live_dynamic_ports(
    workflow: VibeWorkflow,
    *,
    target_schema_provider: Any,
    diagnostics: list[dict[str, Any]],
) -> bool:
    """Refresh dynamic/autogrow input rosters through the existing port contract."""
    from vibecomfy.porting.endpoint_invariant import (
        contracted_dynamic_input_names,
        schema_input_sockets_for_unwired_node,
    )

    changed = False
    for node in workflow.nodes.values():
        getter = getattr(target_schema_provider, "get_schema", None)
        schema = getter(node.class_type) if callable(getter) else None
        if schema is None:
            continue
        fields = dict(node.inputs)
        fields.update(node.widgets)
        dynamic_names = contracted_dynamic_input_names(
            node.class_type, node=node.__dict__ if hasattr(node, "__dict__") else None,
            fields=fields, schema=schema,
        )
        if not dynamic_names:
            continue
        sockets = schema_input_sockets_for_unwired_node(
            schema, node.class_type, fields=fields
        )
        names = [str(item["name"]) for item in sockets if item.get("name") is not None]
        if not names:
            continue
        types = [str(item.get("type") or "*") for item in sockets]
        optional = [
            not bool(getattr(schema.inputs.get(name), "required", False))
            if isinstance(getattr(schema, "inputs", None), Mapping) and name in schema.inputs
            else True
            for name in names
        ]
        if node.native_input_names != names:
            node.native_input_names = names
            node.native_input_types = types
            node.native_input_optional = optional
            changed = True
            diagnostics.append({
                "code": "dynamic_ports_materialized",
                "node_id": str(node.id),
                "class_type": str(node.class_type),
                "input_names": list(names),
                "source": "live_object_info_and_authored_dynamic_contract",
            })
    return changed


def _recompute_projections(workflow: VibeWorkflow) -> dict[str, Any]:
    """Run the existing semantic and execution projection machinery once."""
    semantic = workflow.semantic_projection()
    execution = workflow._execution_projection()
    return {
        "semantic_edges": copy.deepcopy(semantic["edges"]),
        "virtual_wires": copy.deepcopy(semantic["virtual_wires"]),
        "execution_edge_count": len(execution.edges),
        "execution_node_count": len(execution.nodes),
    }


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _publish_reconciled_bundle(
    bundle: WorkflowBundle,
    workflow: VibeWorkflow,
    *,
    diagnostics: list[dict[str, Any]],
) -> WorkflowBundle:
    path = bundle.python_path
    if path is None:
        return _make_bundle(
            workflow,
            python_path=None,
            ui_sidecar=bundle.ui_sidecar,
            provenance=bundle.provenance,
            operation="captured",
            parent_revision=bundle.revision_id,
            parent_evidence={"revision_id": bundle.revision_id, "workflow_identity": workflow.id},
            authority_kind="canonical",
        )
    path = Path(path)
    # The bundle contract deliberately has a closed operation vocabulary;
    # this target refresh is a captured successor revision, not a new authority
    # kind.
    operation = "captured"
    provenance = dict(bundle.provenance)
    provenance["operation"] = operation
    provenance_value = provenance.get("provenance")
    if not isinstance(provenance_value, Mapping):
        provenance_value = {"source": "live_object_info"}
    provenance["provenance"] = dict(provenance_value)
    candidate = _presentation_candidate(bundle)
    sidecar = _build_v2_sidecar(
        workflow,
        candidate,
        provenance=provenance,
        operation=operation,
        parent_revision=bundle.revision_id,
        presentation_diagnostics=diagnostics,
    )
    emitted = workflow.copy()
    emitted.metadata["source_bundle"] = _v2_marker(sidecar)
    emitted.metadata["operation"] = operation
    emitted.metadata["provenance"] = dict(provenance["provenance"])
    emitted.metadata["companion_diagnostics"] = copy.deepcopy(diagnostics)
    from vibecomfy.porting.emit import emit_scratchpad_python

    source = emit_scratchpad_python(
        emitted,
        workflow_id=workflow.id,
        source_path=str(path),
        provenance=provenance,
        external_custody=True,
    )
    _generated_metadata_expressions(source.encode("utf-8"))
    expected = _make_bundle(
        workflow,
        python_path=path,
        ui_sidecar=sidecar,
        provenance=provenance,
        operation=operation,
        parent_revision=bundle.revision_id,
        parent_evidence={"revision_id": bundle.revision_id, "workflow_identity": workflow.id},
        authority_kind="canonical",
    )
    sidecar_path = _sidecar_path(path)
    _atomic_publish_pair(
        path,
        source,
        sidecar,
        expected=expected,
        expected_members={
            path: _sha256_file(path),
            sidecar_path: _sha256_file(sidecar_path),
        },
    )
    from vibecomfy.security.provenance import Provenance
    from vibecomfy.workflow_bundle import load_bundle

    reloaded = load_bundle(
        path,
        trust=Provenance.USER_CONFIRMED,
        allow_unresolved=True,
    )
    if reloaded.workflow.id != workflow.id:
        raise ReconciliationError("reloaded reconciled source changed workflow identity")
    return reloaded


def reconcile_before_queue(
    bundle: WorkflowBundle,
    *,
    target_schema_provider: Any,
    target_schema_generation: str | int | None = None,
    publish: bool = True,
    _captured_identity: tuple[str, str, dict[str, Any]] | None = None,
) -> ReconciliationResult:
    """Capture live schema and admit/apply only source-evidenced widget moves."""
    if not isinstance(bundle, WorkflowBundle):
        raise TypeError("reconciliation requires a WorkflowBundle")
    if _captured_identity is None:
        digest, generation, schema = _live_schema_identity(target_schema_provider)
    else:
        digest, generation, schema = _captured_identity
    if target_schema_generation is not None:
        generation = str(target_schema_generation)
        schema = {**schema, "generation": generation}
    # Keep the runtime package importable while ingest is importing the schema
    # provider.  Snapshot capture itself imports normalization/schema modules,
    # so this dependency belongs at the reconciliation boundary, not module
    # import time.
    from vibecomfy.ingest.snapshot import historical_widget_evidence_by_uid

    workflow = bundle.workflow.copy()
    evidence_by_uid = historical_widget_evidence_by_uid(workflow)
    decisions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    changed = False
    admitted: list[tuple[str, HistoricalWidgetReconciliation]] = []
    for node_id, node in workflow.nodes.items():
        synthetic = any(
            str(key).startswith("widget_")
            for store_name in ("widgets", "inputs")
            for key in getattr(node, store_name, {})
        )
        if not synthetic:
            continue
        uid = str(getattr(node, "uid", "") or node_id)
        evidence = evidence_by_uid.get(uid)
        if evidence is None:
            diagnostic = {
                "code": "missing_historical_widget_evidence",
                "node_id": str(node_id),
                "class_type": str(node.class_type),
                "message": "synthetic widget_N values have no retained source roster/schema evidence",
            }
            diagnostics.append(diagnostic)
            raise ReconciliationError(diagnostic["message"], diagnostics=diagnostics)
        target_node = {
            "class_type": str(node.class_type),
            "widgets_values": _widget_values(node),
        }
        try:
            decision = admit_historical_widget_mappings(
                evidence,
                target_node=target_node,
                target_schema_provider=target_schema_provider,
                target_schema_digest=digest,
                target_schema_generation=generation,
            )
        except HistoricalWidgetMappingRefused as exc:
            diagnostics.append(exc.diagnostic.to_dict())
            raise ReconciliationError(str(exc), diagnostics=diagnostics) from exc
        admitted.append((str(node_id), decision))
        decisions.append(decision.to_dict())

    for node_id, decision in admitted:
        conflicts = _mapping_conflicts(workflow, node_id, decision)
        if conflicts:
            diagnostics.extend(conflicts)
            raise ReconciliationError(
                "widget reconciliation found conflicting authored inputs",
                diagnostics=diagnostics,
            )
    for node_id, decision in admitted:
        changed = _apply_mapping(workflow, node_id, decision) or changed

    changed = _materialize_live_dynamic_ports(
        workflow,
        target_schema_provider=target_schema_provider,
        diagnostics=diagnostics,
    ) or changed

    # This is the single semantic refresh after the target mapping. It
    # re-registers public inputs/requirements while retaining Python-owned
    # edges and virtual wires; the companion remains presentation-only.
    if changed:
        workflow.finalize_metadata()
    projection = _recompute_projections(workflow)
    workflow.metadata["reconciliation"] = {
        "status": "changed" if changed else "unchanged",
        "target_schema_digest": digest,
        "target_schema_generation": generation,
        "decisions": copy.deepcopy(decisions),
        "diagnostics": copy.deepcopy(diagnostics),
        **projection,
    }
    if not changed and not bundle.unresolved:
        reconciled = bundle
    elif publish:
        reconciled = _publish_reconciled_bundle(
            bundle, workflow, diagnostics=diagnostics
        )
    else:
        reconciled = _make_bundle(
            workflow,
            python_path=bundle.python_path,
            ui_sidecar=bundle.ui_sidecar,
            provenance=bundle.provenance,
            operation="captured",
            parent_revision=bundle.revision_id,
            parent_evidence={"revision_id": bundle.revision_id, "workflow_identity": workflow.id},
            authority_kind="canonical",
        )
    return ReconciliationResult(
        bundle=reconciled,
        changed=changed,
        schema=schema,
        decisions=tuple(decisions),
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "ExecutionSnapshot",
    "ReconciliationError",
    "ReconciliationResult",
    "assert_execution_snapshot",
    "build_execution_snapshot",
    "reconcile_before_queue",
    "reconcile_before_queue_async",
]
