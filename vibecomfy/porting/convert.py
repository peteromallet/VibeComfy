from __future__ import annotations

import copy
import difflib
import importlib.util
import logging
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibecomfy.porting.emitter import (
    EmissionDiagnostic,
    EmissionSeverity,
    emit_ready_template_python,
    emit_scratchpad_python,
)
from vibecomfy.porting.object_info.consume import ObjectInfoIdentity
from vibecomfy.porting.helper_resolve import ResolveDiagnostics, resolve_helpers
from vibecomfy.porting.parity import (
    class_type_counter,
    compile_equivalent,
    topology_counter,
    widget_value_counter,
)
from vibecomfy.porting.report import PortIssue
from vibecomfy.custom_node_refs import normalize_custom_node_requirements, structured_refs_from_lock_entries
from vibecomfy.node_packs_lockfile import read_lockfile
from vibecomfy.porting.strict_ready import (
    STRICT_READY_BUILD_FAILED,
    STRICT_READY_COMPILE_FAILED,
    StrictReadyContext,
    validate_strict_ready_workflow,
)
from vibecomfy.porting.widget_aliases import widget_alias_analysis
from vibecomfy.utils import repo_relative_path
from vibecomfy.workflow import ValidationIssue, ValidationReport, VibeWorkflow

# -- model-like value detection ----------------------------------------------

_MODEL_LIKE_EXTENSIONS: frozenset[str] = frozenset(
    {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx"}
)
_PROVENANCE_PATH_KEYS: frozenset[str] = frozenset({"source_path", "source_workflow_path", "source_workflow"})
logger = logging.getLogger(__name__)


PortConvertMode = Literal["scratchpad", "ready_template"]


@dataclass(slots=True)
class PortConvertValidation:
    ok: bool
    import_ok: bool = False
    build_ok: bool = False
    compile_ok: bool = False
    schema_ok: bool | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    api_node_count: int = 0
    error: str | None = None

    # Parity evidence (populated when source and emitted are both compiled)
    parity_ok: bool | None = None
    parity_error: str | None = None
    parity_diffs: list[str] = field(default_factory=list)
    source_output_count: int = 0
    emitted_output_count: int = 0
    source_class_type_counts: dict[str, int] = field(default_factory=dict)
    emitted_class_type_counts: dict[str, int] = field(default_factory=dict)
    source_widget_value_snapshot: int = 0  # distinct (class, key, repr) count
    emitted_widget_value_snapshot: int = 0
    source_topology_snapshot: int = 0  # distinct (class, input, source_class, slot) count
    emitted_topology_snapshot: int = 0

    # Readability diagnostics collected during emission
    emission_diagnostics: list[EmissionDiagnostic] = field(default_factory=list)

    # True when conversion emitted ``unprovenanced_class_fallback`` or
    # ``provenance_identity_cache_miss`` warnings — downstream tooling must
    # treat the resulting graph as low-confidence (e.g., the emitted template
    # may not faithfully reflect the pinned object_info schema).
    low_confidence: bool = False

    # Model-like value comparison
    model_value_change: bool = False
    """True when aliasing changed a model-like value between source and emitted."""
    model_value_dropped: bool = False
    """True when a model-like value present in source is absent from emitted."""
    hidden_model_filenames: list[str] = field(default_factory=list)
    """Model filenames only present under widget_N keys that cannot be aliased."""
    source_model_snapshot: dict[str, str] = field(default_factory=dict)
    """{(node_id, key): value} snapshot of model-like values from source API."""
    emitted_model_snapshot: dict[str, str] = field(default_factory=dict)
    """{(node_id, key): value} snapshot of model-like values from emitted API."""
    ready_requirements_model_snapshot: list[str] = field(default_factory=list)
    """Model-like values from READY_REQUIREMENTS['models'] for ready templates."""
    workflow_requirements_model_snapshot: list[str] = field(default_factory=list)
    """Model-like values declared by workflow.requirements.models."""
    metadata_model_snapshot: list[str] = field(default_factory=list)
    """Model-like values declared by READY_METADATA['model_assets']."""
    model_value_diffs: list[str] = field(default_factory=list)
    """Human-readable diffs between source and emitted model values."""

    strict_ready_ok: bool | None = None
    """Ready-template candidate strict-ready status, if applicable."""
    strict_ready_diagnostics: list[PortIssue] = field(default_factory=list)
    """Strict-ready diagnostics for emitted ready-template candidates."""

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "import_ok": self.import_ok,
            "build_ok": self.build_ok,
            "compile_ok": self.compile_ok,
            "schema_ok": self.schema_ok,
            "issues": [asdict(issue) for issue in self.issues],
            "api_node_count": self.api_node_count,
            "error": self.error,
            "parity_ok": self.parity_ok,
            "parity_error": self.parity_error,
            "parity_diffs": self.parity_diffs,
            "source_output_count": self.source_output_count,
            "emitted_output_count": self.emitted_output_count,
            "source_class_type_counts": self.source_class_type_counts,
            "emitted_class_type_counts": self.emitted_class_type_counts,
            "source_widget_value_snapshot": self.source_widget_value_snapshot,
            "emitted_widget_value_snapshot": self.emitted_widget_value_snapshot,
            "source_topology_snapshot": self.source_topology_snapshot,
            "emitted_topology_snapshot": self.emitted_topology_snapshot,
            "emission_diagnostics": [d.to_json() for d in self.emission_diagnostics],
            "low_confidence": self.low_confidence,
            "model_value_change": self.model_value_change,
            "model_value_dropped": self.model_value_dropped,
            "hidden_model_filenames": self.hidden_model_filenames,
            "source_model_snapshot": self.source_model_snapshot,
            "emitted_model_snapshot": self.emitted_model_snapshot,
            "ready_requirements_model_snapshot": self.ready_requirements_model_snapshot,
            "workflow_requirements_model_snapshot": self.workflow_requirements_model_snapshot,
            "metadata_model_snapshot": self.metadata_model_snapshot,
            "model_value_diffs": self.model_value_diffs,
            "strict_ready_ok": self.strict_ready_ok,
            "strict_ready_diagnostics": [issue.to_json() for issue in self.strict_ready_diagnostics],
        }


@dataclass(slots=True)
class PortConvertResult:
    mode: PortConvertMode
    text: str
    ready_id: str | None = None
    validation: PortConvertValidation | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ready_id": self.ready_id,
            "validation": self.validation.to_json() if self.validation is not None else None,
        }


# Get/Set broadcast wires + Reroute passthrough are the virtual-wire nodes whose
# stable channel name (not the edge) is the routing key. PrimitiveNode is a value
# helper, not a wire, so it is intentionally excluded here.
_VIRTUAL_WIRE_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode", "Reroute"})


def _capture_virtual_wires(workflow: VibeWorkflow) -> dict[str, dict[str, Any]]:
    """Snapshot Get/Set/Reroute virtual-wire nodes BEFORE helper resolution.

    Captures uid, type, channel name, pos/size, and the routed endpoints for each
    virtual-wire node, keyed by uid. This must run before both
    ``resolve_subgraph_helpers`` and ``resolve_helpers`` (which delete these nodes
    in place). Returns ``{}`` when the graph has no virtual-wire nodes.
    """
    from vibecomfy._workflow_helpers import (
        BROADCAST_HELPER_CLASS_TYPES,
        broadcast_name,
    )

    captured: dict[str, dict[str, Any]] = {}
    for node_id, node in workflow.nodes.items():
        if node.class_type not in _VIRTUAL_WIRE_CLASS_TYPES:
            continue
        uid = node.uid or str(node_id)
        ui = node.metadata.get("_ui") if isinstance(node.metadata, dict) else None
        pos = ui.get("pos") if isinstance(ui, dict) else None
        size = ui.get("size") if isinstance(ui, dict) else None
        channel = (
            broadcast_name(node)
            if node.class_type in BROADCAST_HELPER_CLASS_TYPES
            else None
        )
        endpoints = [
            [edge.from_node, edge.from_output, edge.to_node, edge.to_input]
            for edge in workflow.edges
            if str(edge.from_node) == str(node_id) or str(edge.to_node) == str(node_id)
        ]
        captured[uid] = {
            "type": node.class_type,
            "channel": channel,
            "pos": pos,
            "size": size,
            "endpoints": endpoints,
        }
    return captured


def _node_object_info_identities(raw_workflow: dict[str, Any]) -> dict[str, ObjectInfoIdentity]:
    """Derive a node_id -> ObjectInfoIdentity map from raw workflow provenance.

    Uses the shared provenance requirement builder, independent of ensure-env.
    Returns an empty dict when provenance data is absent or unparseable.
    """
    from vibecomfy.porting.provenance import extract_provenance

    try:
        report = extract_provenance(raw_workflow)
    except Exception:
        return {}

    result: dict[str, ObjectInfoIdentity] = {}
    for req in report.requirements:
        pack_slug: str | None = req.cnr_id
        if not pack_slug and req.aux_id:
            # Use owner/repo from aux_id as the slug (no registry cnr_id)
            pack_slug = req.aux_id
        if not pack_slug:
            continue
        git_commit: str | None = None
        if req.version_pin is not None:
            git_commit = req.version_pin.version or None
        identity = ObjectInfoIdentity(
            pack_slug=pack_slug,
            git_commit=git_commit,
            evidence_identity=req.identity_key or None,
        )
        for node_id in req.node_ids:
            result[node_id] = identity
    return result


def port_convert_workflow(
    workflow: VibeWorkflow,
    *,
    ready_id: str | None = None,
    source_path: str | None = None,
    provenance: dict[str, Any] | None = None,
    source_hash: str | None = None,
    workflow_shape: dict[str, Any] | None = None,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    schema_provider: Any | None = None,
    validate: bool = True,
    raw_workflow: dict[str, Any] | None = None,
    keep_virtual_wires: bool = False,
    prune_dead_branches: bool = True,
) -> PortConvertResult:
    emission_diagnostics: list[EmissionDiagnostic] = []

    # ── Resolve helper nodes before emission ────────────────────────────
    # Normalise the caller-owned dict so the resolver can populate it with
    # name -> (consumer_node_id, consumer_field) entries for named
    # single-consumer primitives promoted to public inputs.
    registered_inputs = dict(registered_inputs or {})

    # Collect broadcast sources *before* the top-level resolver strips
    # SetNode nodes.  Subgraph helpers (GetNode inside UUID subgraph
    # definitions) need the original top-level broadcast map to resolve
    # their sources.  Capturing this snapshot avoids a use-after-delete
    # race between resolve_helpers (which deletes SetNode) and
    # resolve_subgraph_helpers (which needs SetNode broadcast data).
    from vibecomfy._workflow_helpers import collect_broadcast_sources as _collect_broadcasts
    _pre_resolve_broadcasts = _collect_broadcasts(workflow.nodes, workflow.edges)

    # ── M2 Step 8: snapshot furniture BEFORE any helper resolution ──────
    # resolve_subgraph_helpers (below) and resolve_helpers (further down)
    # both delete Get/Set/Reroute and subgraph-inner nodes in place. Snapshot
    # the data needed to reconstruct the editor view into workflow.metadata
    # *before* that deletion. This is metadata-only — nothing reaches the
    # execution API graph, so compile('api') stays byte-identical.
    _virtual_wires = _capture_virtual_wires(workflow)
    if _virtual_wires:
        workflow.metadata["virtual_wires"] = _virtual_wires

    # Resolve helper nodes inside UUID subgraph definitions FIRST, using
    # the pre-resolve broadcast snapshot.  Subgraph helpers reference
    # top-level SetNode broadcasts; if we resolve top-level helpers first,
    # SetNode nodes are deleted and the subgraph resolver finds nothing.
    if raw_workflow is not None:
        # Deep-copy the raw subgraph definitions before resolution mutates the
        # graph. Graceful absence: store nothing when 'definitions' is missing.
        _definitions = raw_workflow.get("definitions")
        if _definitions is not None:
            workflow.metadata["definitions"] = copy.deepcopy(_definitions)

        from vibecomfy.porting.subgraph_resolve import resolve_subgraph_helpers
        resolve_subgraph_helpers(
            raw_workflow,
            workflow.nodes,
            workflow.edges,
            _pre_resolve_broadcasts,
        )

    # resolve_helpers mutates workflow.nodes/workflow.edges in place and
    # populates *registered_inputs*.  This runs *before* the compile('api')
    # parity capture at line ~203, so both source_api and the emitted
    # module's build() compile the post-resolution graph.  Parity therefore
    # validates emission fidelity of the resolved graph, not semantic
    # preservation against the raw source.  Resolver-vs-source correctness
    # is guaranteed by the Step 3.6 hard error and the Step 9 runexx oracle.
    #
    # When keep_virtual_wires=True, skip resolution so GetNode/SetNode/Reroute
    # pass through to the emitter as explicit wf.node(...) calls.
    if keep_virtual_wires:
        resolve_diagnostics: ResolveDiagnostics = ResolveDiagnostics()
    else:
        resolve_diagnostics = resolve_helpers(workflow, registered_inputs)

    # Surface ResolveDiagnostics into the existing emission_diagnostics
    # channel (FG-005): convert each HelperDiagnostic into an
    # EmissionDiagnostic so they flow through the standard
    # PortConvertValidation.to_json() reporting path.
    from vibecomfy._workflow_helpers import HelperDiagnostic

    for hd in resolve_diagnostics.diagnostics:
        sev: EmissionSeverity = "warning"
        if hd.severity == "info":
            sev = "info"
        elif hd.severity == "error":
            sev = "error"
        emission_diagnostics.append(
            EmissionDiagnostic(
                code=f"resolve_{hd.code}",
                message=hd.message,
                severity=sev,
                node_id=hd.node_id,
                class_type=hd.class_type,
                detail=hd.detail,
            )
        )

    # Derive node-level object-info identities from the raw workflow via the
    # shared provenance requirement builder, independent of ensure-env.
    object_info_identities: dict[str, ObjectInfoIdentity] | None = None
    if raw_workflow is not None:
        object_info_identities = _node_object_info_identities(raw_workflow) or None

    if ready_id is None:
        complete_provenance = _conversion_provenance(
            workflow,
            source_path=source_path,
            provenance=provenance,
            source_hash=source_hash,
            workflow_shape=workflow_shape,
            output_mode="scratchpad",
            ready_id=None,
        )
        text = emit_scratchpad_python(
            workflow,
            workflow_id=workflow.id,
            source_path=source_path,
            provenance=complete_provenance,
            registered_inputs=registered_inputs,
            diagnostics=emission_diagnostics,
            keep_virtual_wires=keep_virtual_wires,
            prune_dead_branches=prune_dead_branches,
            object_info_identities=object_info_identities,
        )
        mode: PortConvertMode = "scratchpad"
    else:
        _validate_ready_id(ready_id)
        complete_provenance = _conversion_provenance(
            workflow,
            source_path=source_path,
            provenance=provenance,
            source_hash=source_hash,
            workflow_shape=workflow_shape,
            output_mode="ready_template",
            ready_id=ready_id,
        )
        text = emit_ready_template_python(
            workflow,
            ready_metadata=_ready_metadata(workflow, ready_id=ready_id, source_path=source_path, provenance=complete_provenance),
            ready_requirements=_ready_requirements(workflow),
            template_id=ready_id,
            registered_inputs=registered_inputs,
            diagnostics=emission_diagnostics,
            raw_workflow=raw_workflow,
            object_info_identities=object_info_identities,
        )
        mode = "ready_template"

    # Compile the source workflow before emission for parity comparison.
    source_api = workflow.compile("api") if validate else None

    # Build class_widget_aliases from source workflow node metadata for
    # parity canonicalization.  This uses schema-source evidence (from the
    # conversion schema provider) rather than the static WIDGET_SCHEMA so
    # the comparison cannot mask incorrect aliases by canonicalising both
    # sides through the same (potentially wrong) static table.
    #
    # Precedence: (1) node metadata input_aliases, (2) schema_provider.
    class_widget_aliases: dict[str, list[str | None]] = {}
    seen_classes: set[str] = set()
    for node in workflow.nodes.values():
        ct = node.class_type
        if ct in seen_classes:
            continue
        seen_classes.add(ct)
        aliases = getattr(node, "metadata", {}).get("input_aliases")
        if isinstance(aliases, (list, tuple)) and aliases:
            class_widget_aliases[ct] = list(aliases)
        elif schema_provider is not None:
            try:
                from vibecomfy.porting.widget_aliases import LINK_ONLY_TYPES
                schema = schema_provider.get_schema(ct) if hasattr(schema_provider, "get_schema") else None
                if schema is not None:
                    inputs = getattr(schema, "inputs", None)
                    if isinstance(inputs, dict):
                        provider_aliases: list[str | None] = []
                        for name, spec in inputs.items():
                            input_type = str(getattr(spec, "type", "") or "").upper()
                            if input_type in LINK_ONLY_TYPES:
                                continue
                            provider_aliases.append(str(name))
                        if provider_aliases:
                            class_widget_aliases[ct] = provider_aliases
            except Exception:
                # Alias collection is best-effort conversion evidence, not a
                # parity failure. Keep this out of the loud parity-error path
                # unless focused schema-provider tests prove it masks a bug.
                pass

    result = PortConvertResult(mode=mode, text=text, ready_id=ready_id)
    if validate:
        result.validation = validate_emitted_module(text, schema_provider=schema_provider)
        result.validation.emission_diagnostics = emission_diagnostics
        if any(
            d.code in ("unprovenanced_class_fallback", "provenance_identity_cache_miss")
            for d in emission_diagnostics
        ):
            result.validation.low_confidence = True
        if ready_id is not None and result.validation is not None:
            _run_strict_ready_candidate_validation(
                result.validation,
                text,
                ready_id=ready_id,
                source_path=source_path,
                schema_provider=schema_provider,
            )

        # Run parity: compile the emitted module and compare against source.
        if source_api is not None and result.validation is not None and result.validation.compile_ok:
            try:
                with tempfile.TemporaryDirectory(prefix="vibecomfy-port-parity-") as tmp:
                    parity_path = Path(tmp) / "emitted_parity.py"
                    parity_path.write_text(text, encoding="utf-8")
                    spec = importlib.util.spec_from_file_location(
                        f"vibecomfy_port_parity_{parity_path.stem}", parity_path
                    )
                    if spec is not None and spec.loader is not None:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        build_fn = getattr(module, "build", None)
                        if callable(build_fn):
                            emitted_wf = build_fn()
                            if isinstance(emitted_wf, VibeWorkflow):
                                emitted_api = emitted_wf.compile("api")
                                parity_ok, parity_diffs = compile_equivalent(
                                    source_api, emitted_api,
                                    class_widget_aliases=class_widget_aliases,
                                )

                                result.validation.parity_ok = parity_ok
                                result.validation.parity_diffs = parity_diffs

                                # Output counts
                                result.validation.source_output_count = len(source_api)
                                result.validation.emitted_output_count = len(emitted_api)

                                # Class type snapshots
                                src_ct = class_type_counter(source_api)
                                emit_ct = class_type_counter(emitted_api)
                                result.validation.source_class_type_counts = dict(src_ct)
                                result.validation.emitted_class_type_counts = dict(emit_ct)

                                # Widget value snapshots (distinct count)
                                src_wv = widget_value_counter(source_api)
                                emit_wv = widget_value_counter(emitted_api)
                                result.validation.source_widget_value_snapshot = len(src_wv)
                                result.validation.emitted_widget_value_snapshot = len(emit_wv)

                                # Topology snapshots (distinct count)
                                src_topo = topology_counter(source_api)
                                emit_topo = topology_counter(emitted_api)
                                result.validation.source_topology_snapshot = len(src_topo)
                                result.validation.emitted_topology_snapshot = len(emit_topo)

                                # -- model-like value comparison --------
                                _run_model_value_comparison(
                                    result.validation,
                                    source_api,
                                    emitted_api,
                                    workflow,
                                    ready_id=ready_id,
                                )
            except Exception as exc:
                parity_error = f"{type(exc).__name__}: {exc}"
                result.validation.ok = False
                result.validation.parity_ok = False
                result.validation.parity_error = parity_error
                if result.validation.error is None:
                    result.validation.error = f"parity check failed: {parity_error}"

    return result


def _run_strict_ready_candidate_validation(
    validation: PortConvertValidation,
    text: str,
    *,
    ready_id: str,
    source_path: str | None,
    schema_provider: Any | None,
) -> None:
    if not validation.import_ok or not validation.build_ok or not validation.compile_ok:
        code = STRICT_READY_BUILD_FAILED
        if validation.error and validation.error.startswith("compile failed:"):
            code = STRICT_READY_COMPILE_FAILED
        validation.strict_ready_diagnostics = [
            PortIssue(
                code=code,
                message=f"Strict ready-template candidate could not be validated: {validation.error or 'unknown error'}",
                severity="error",
                detail={
                    "category": "strict_ready",
                    "target": "candidate_build",
                    "ready_id": ready_id,
                },
                recommendation="Fix emitted ready-template import/build/compile errors before writing the target file.",
            )
        ]
        validation.strict_ready_ok = False
        validation.ok = False
        if validation.error is None:
            validation.error = "strict-ready candidate validation failed"
        return

    try:
        emitted_workflow = _build_emitted_workflow_from_text(text)
        emitted_api = emitted_workflow.compile("api")
    except Exception as exc:
        validation.strict_ready_diagnostics = [
            PortIssue(
                code=STRICT_READY_BUILD_FAILED,
                message=f"Strict ready-template candidate build failed: {type(exc).__name__}: {exc}",
                severity="error",
                detail={
                    "category": "strict_ready",
                    "target": "candidate_build",
                    "ready_id": ready_id,
                },
                recommendation="Fix emitted ready-template build errors before writing the target file.",
            )
        ]
        validation.strict_ready_ok = False
        validation.ok = False
        validation.error = validation.error or "strict-ready candidate validation failed"
        return

    diagnostics = validate_strict_ready_workflow(
        emitted_workflow,
        StrictReadyContext(
            ready_id=ready_id,
            source_path=source_path,
            is_post_resolution=True,
        ),
        api_prompt=emitted_api,
        widget_analysis=widget_alias_analysis(emitted_api, schema_provider=schema_provider),
    )
    validation.strict_ready_diagnostics = diagnostics
    validation.strict_ready_ok = not any(issue.severity == "error" for issue in diagnostics)
    if not validation.strict_ready_ok:
        validation.ok = False
        validation.error = validation.error or "strict-ready candidate validation failed"


def _build_emitted_workflow_from_text(text: str) -> VibeWorkflow:
    with tempfile.TemporaryDirectory(prefix="vibecomfy-port-strict-ready-") as tmp:
        path = Path(tmp) / "emitted.py"
        path.write_text(text, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(f"vibecomfy_port_strict_ready_{path.stem}", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not import emitted module {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        build = getattr(module, "build", None)
        if not callable(build):
            raise RuntimeError("build() missing")
        workflow = build()
        if not isinstance(workflow, VibeWorkflow):
            raise RuntimeError(f"build() returned {type(workflow).__name__}, expected VibeWorkflow")
        return workflow


def validate_emitted_module(text: str, *, schema_provider: Any | None = None) -> PortConvertValidation:
    with tempfile.TemporaryDirectory(prefix="vibecomfy-port-convert-") as tmp:
        path = Path(tmp) / "emitted.py"
        path.write_text(text, encoding="utf-8")
        return _validate_emitted_path(path, schema_provider=schema_provider)


def _validate_emitted_path(path: Path, *, schema_provider: Any | None) -> PortConvertValidation:
    try:
        spec = importlib.util.spec_from_file_location(f"vibecomfy_port_convert_{path.stem}", path)
        if spec is None or spec.loader is None:
            return PortConvertValidation(ok=False, error=f"Could not import emitted module {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        return PortConvertValidation(ok=False, error=f"import failed: {type(exc).__name__}: {exc}")

    build = getattr(module, "build", None)
    if not callable(build):
        return PortConvertValidation(ok=False, import_ok=True, error="build() missing")

    try:
        workflow = build()
    except Exception as exc:
        return PortConvertValidation(ok=False, import_ok=True, error=f"build failed: {type(exc).__name__}: {exc}")
    if not isinstance(workflow, VibeWorkflow):
        return PortConvertValidation(
            ok=False,
            import_ok=True,
            error=f"build() returned {type(workflow).__name__}, expected VibeWorkflow",
        )

    try:
        api = workflow.compile("api")
    except Exception as exc:
        return PortConvertValidation(
            ok=False,
            import_ok=True,
            build_ok=True,
            error=f"compile failed: {type(exc).__name__}: {exc}",
        )

    report = workflow.validate(schema_provider=schema_provider) if schema_provider is not None else ValidationReport(ok=True)
    return PortConvertValidation(
        ok=report.ok,
        import_ok=True,
        build_ok=True,
        compile_ok=True,
        schema_ok=report.ok if schema_provider is not None else None,
        issues=report.issues,
        api_node_count=len(api),
        error=None if report.ok else "schema validation failed",
    )


def _source_provenance(workflow: VibeWorkflow, *, source_path: str | None) -> dict[str, Any]:
    provenance = dict(workflow.source.provenance)
    if source_path is not None:
        provenance.setdefault("source_path", _repo_relative_provenance_path(source_path))
    provenance.setdefault("source_id", workflow.source.id)
    provenance.setdefault("source_type", workflow.source.source_type)
    if workflow.source.path is not None:
        provenance.setdefault("source_workflow_path", _repo_relative_provenance_path(workflow.source.path))
    return _normalize_provenance_paths(provenance)


def _conversion_provenance(
    workflow: VibeWorkflow,
    *,
    source_path: str | None,
    provenance: dict[str, Any] | None,
    source_hash: str | None,
    workflow_shape: dict[str, Any] | None,
    output_mode: PortConvertMode,
    ready_id: str | None,
) -> dict[str, Any]:
    merged = _source_provenance(workflow, source_path=source_path)
    if provenance:
        merged.update(provenance)
    if source_hash is not None:
        merged["source_hash"] = source_hash
    if workflow_shape is not None:
        merged["workflow_shape"] = dict(workflow_shape)
    merged["output_mode"] = output_mode
    if ready_id is not None:
        merged["ready_id"] = ready_id
    return merged


def _validate_ready_id(ready_id: str) -> None:
    parts = ready_id.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError("ready_id must have the form 'kind/name'")


_SAGEATTENTION_CLASS_TYPES = frozenset({
    "LTX2MemoryEfficientSageAttentionPatch",
    "PathchSageAttentionKJ",
})


def _ensure_sageattention_runtime_package(
    metadata: dict[str, Any],
    workflow: VibeWorkflow,
) -> None:
    """Add ``sageattention`` to ``runtime_packages`` when SageAttention nodes are present.

    Only mutates *metadata* when (a) the workflow references one of the known
    SageAttention class types and (b) ``runtime_packages`` does not already
    contain a ``sageattention`` entry.
    """
    has_sage_node = any(
        node.class_type in _SAGEATTENTION_CLASS_TYPES
        for node in workflow.nodes.values()
    )
    if not has_sage_node:
        return
    existing = metadata.get("runtime_packages")
    if isinstance(existing, list) and any(
        isinstance(pkg, dict) and pkg.get("name") == "sageattention"
        for pkg in existing
    ):
        return
    entry = {
        "name": "sageattention",
        "reason": (
            "Required by LTX2MemoryEfficientSageAttentionPatch / "
            "PathchSageAttentionKJ for memory-efficient attention on "
            "compatible GPUs."
        ),
        "source": "SageAttention-ada",
    }
    if isinstance(existing, list):
        metadata["runtime_packages"] = [*existing, entry]
    else:
        metadata["runtime_packages"] = [entry]


def _ready_metadata(
    workflow: VibeWorkflow,
    *,
    ready_id: str,
    source_path: str | None,
    provenance: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = dict(workflow.metadata)
    metadata["ready_template"] = ready_id
    if source_path is not None:
        metadata.setdefault("source_workflow", _repo_relative_provenance_path(source_path))
    if provenance:
        metadata.setdefault("provenance", _normalize_provenance_paths(provenance))
    _ensure_sageattention_runtime_package(metadata, workflow)
    return metadata


def _normalize_provenance_paths(provenance: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(provenance)
    for key in _PROVENANCE_PATH_KEYS:
        value = normalized.get(key)
        if isinstance(value, str) and value:
            normalized[key] = _repo_relative_provenance_path(value)
    return normalized


def _repo_relative_provenance_path(path: str) -> str:
    normalized = repo_relative_path(path)
    if Path(normalized).is_absolute():
        logger.warning("provenance path is outside the repo; keeping absolute path: %s", normalized)
    return normalized


def _ready_requirements(workflow: VibeWorkflow) -> dict[str, Any]:
    model_assets = workflow.metadata.get("model_assets")
    models = model_assets if isinstance(model_assets, list) else list(workflow.requirements.models)
    requirements = {
        "models": models,
        "custom_nodes": list(workflow.requirements.custom_nodes),
    }
    metadata_requirements = workflow.metadata.get("requirements")
    if isinstance(metadata_requirements, dict):
        normalized, _warnings = normalize_custom_node_requirements(metadata_requirements)
        refs = normalized.get("custom_node_refs")
        if isinstance(refs, list) and refs:
            requirements["custom_node_refs"] = refs
            requirements["custom_nodes"] = normalized.get("custom_nodes", requirements["custom_nodes"])
            return requirements
    refs = structured_refs_from_lock_entries(list(workflow.requirements.custom_nodes), read_lockfile())
    if refs:
        requirements["custom_node_refs"] = refs
    return requirements


# ---------------------------------------------------------------------------
# Atomic conversion write - temp file, validate, parity-check, then replace
# ---------------------------------------------------------------------------


class ManualTemplateRefusal(ValueError):
    """Raised when a target file has `# vibecomfy: manual` marker."""


class ConversionWriteError(RuntimeError):
    """Raised when atomic write fails validation or parity gates.

    Rebased onto :class:`~vibecomfy.errors.VibeComfyError` so that
    *failure_reason* and *next_action* are available on every instance while
    keeping backward-compatibility with existing ``except ConversionWriteError``
    sites.
    """

    def __init__(
        self,
        message: str,
        *,
        failure_reason: str | None = None,
        next_action: str | None = None,
    ) -> None:
        self.failure_reason = failure_reason
        self.next_action = next_action
        super().__init__(message)


def _check_manual_refusal(target: Path) -> None:
    """Refuse to overwrite a template marked `# vibecomfy: manual`."""
    if not target.exists():
        return
    first_line = target.read_text(encoding="utf-8").splitlines()[0].strip() if target.exists() else ""
    if "# vibecomfy: manual" in first_line:
        raise ManualTemplateRefusal(
            f"Target {target} is marked '# vibecomfy: manual'. "
            f"Remove the marker or use a different output path."
        )


def _compute_diff(original: str, emitted: str, target_path: str) -> dict[str, Any]:
    """Produce unified diff + JSON diff metadata."""
    original_lines = original.splitlines(keepends=True)
    emitted_lines = emitted.splitlines(keepends=True)
    unified = "".join(
        difflib.unified_diff(
            original_lines if original else [],
            emitted_lines,
            fromfile=str(target_path),
            tofile=f"{target_path} (emitted)",
        )
    )
    return {
        "unified_diff": unified,
        "original_exists": bool(original),
        "emitted_line_count": len(emitted_lines),
        "original_line_count": len(original_lines),
    }


def port_convert_and_write(
    result: "PortConvertResult",
    target: Path,
    *,
    dry_run: bool = False,
    diff: bool = False,
) -> dict[str, Any]:
    """Write emitted text via temp-file atomic replace after all gates pass.

    Args:
        result: The conversion result from `port_convert_workflow`.
        target: Destination file path.
        dry_run: If True, emit conversion payload and evidence without writing.
        diff: If True, produce unified diff + JSON diff metadata (forces dry_run).

    Returns:
        A dict with `written`, `dry_run`, `diff`, and `validation` keys.

    Raises:
        ManualTemplateRefusal: If target has `# vibecomfy: manual` marker.
        ConversionWriteError: If validation or parity fails.
    """
    # Gate 1: manual-template refusal
    _check_manual_refusal(target)

    # Read original content for diff
    original_content = target.read_text(encoding="utf-8") if target.exists() else ""

    # Gate 2: validation must pass
    validation = result.validation
    if validation is None:
        raise ConversionWriteError(
            "No validation available - conversion may have been skipped.",
            next_action="vibecomfy port --validate-only <target>",
        )
    if validation.strict_ready_ok is False:
        strict_errors = [
            issue
            for issue in validation.strict_ready_diagnostics
            if issue.severity == "error"
        ]
        examples = [f"{issue.code}:{issue.detail.get('target', '')}" for issue in strict_errors[:5]]
        raise ConversionWriteError(
            f"Strict-ready validation failed for {target}. "
            f"Diagnostics: {examples}",
            next_action="vibecomfy port --validate-only <target>",
        )
    if not validation.ok:
        raise ConversionWriteError(
            f"Validation failed for {target}: {validation.error}. "
            f"Parity OK: {validation.parity_ok}. "
            f"Fix issues before writing.",
            next_action="vibecomfy port --validate-only <target>",
        )
    if validation.parity_ok is False:
        raise ConversionWriteError(
            f"Parity check failed for {target}. "
            f"Diffs: {validation.parity_diffs[:5]}",
            next_action="vibecomfy port --parity-check <target>",
        )

    # Gate 2b: model-like value change / drop prevents write
    if validation.model_value_change:
        raise ConversionWriteError(
            f"Model-like value changed after aliasing for {target}. "
            f"Diffs: {validation.model_value_diffs[:5]}",
            next_action="vibecomfy port --validate-only <target>",
        )
    if validation.model_value_dropped:
        raise ConversionWriteError(
            f"Model-like value dropped after aliasing for {target}. "
            f"Diffs: {validation.model_value_diffs[:5]}",
            next_action="vibecomfy port --validate-only <target>",
        )

    # Diff mode
    diff_data: dict[str, Any] | None = None
    if diff:
        diff_data = _compute_diff(original_content, result.text, str(target))

    # Dry-run mode
    if dry_run:
        payload: dict[str, Any] = {
            "written": False,
            "dry_run": True,
            "target": str(target),
            "validation": validation.to_json(),
        }
        if diff_data is not None:
            payload["diff"] = diff_data
        else:
            # Always include diff in dry-run
            payload["diff"] = _compute_diff(original_content, result.text, str(target))
        return payload

    # Gate 3: atomic write - temp file in target directory, validate, then replace
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix=".vibecomfy-port-",
        dir=str(target.parent),
        encoding="utf-8",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp_path.write_text(result.text, encoding="utf-8")

    try:
        # Re-validate the temp module before replacing
        temp_validation = _validate_emitted_path(tmp_path, schema_provider=None)
        if not temp_validation.ok and temp_validation.import_ok:
            # Build/compile issues are non-fatal if the original validation passed
            pass
        elif not temp_validation.import_ok:
            raise ConversionWriteError(
                f"Temp file at {tmp_path} failed import validation: {temp_validation.error}",
                next_action="vibecomfy port --validate-only <target>",
            )

        # Atomic replace
        tmp_path.replace(target)
    except Exception:
        # Clean up temp file on failure
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return {
        "written": True,
        "dry_run": False,
        "target": str(target),
        "validation": validation.to_json(),
        "diff": diff_data,
    }


# -- model-like value snapshot & comparison -----------------------------


def _looks_like_model_value(value: Any) -> bool:
    """Return True when *value* is a string that looks like a model filename."""
    if not isinstance(value, str):
        return False
    lower = value.lower()
    for ext in _MODEL_LIKE_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


def snapshot_model_values(api: dict) -> dict[tuple[str, str], str]:
    """Extract model-like values from a compiled API dict.

    Returns `{(node_id, input_key): value}` for every input whose value
    looks like a model filename (e.g. `.safetensors`, `.ckpt`).
    """
    models: dict[tuple[str, str], str] = {}
    for node_id, node in api.items():
        for key, value in node.get("inputs", {}).items():
            if _looks_like_model_value(value):
                models[(str(node_id), key)] = str(value)
    return models


def _detect_hidden_model_filenames(
    source_api: dict,
    class_widget_aliases: dict[str, list[str | None]],
) -> list[str]:
    """Find model filenames only referenced under `widget_N` keys."""
    hidden: list[str] = []
    for _node_id, node in source_api.items():
        class_type = node.get("class_type", "")
        widget_model_values: dict[int, str] = {}
        named_model_values: set[str] = set()

        for key, value in node.get("inputs", {}).items():
            if not _looks_like_model_value(value):
                continue
            if key.startswith("widget_"):
                try:
                    idx = int(key.split("_", 1)[1])
                    widget_model_values[idx] = str(value)
                except ValueError:
                    named_model_values.add(str(value))
            else:
                named_model_values.add(str(value))

        aliases = class_widget_aliases.get(class_type)
        for idx, val in widget_model_values.items():
            if val in named_model_values:
                continue
            if aliases is not None and 0 <= idx < len(aliases):
                alias = aliases[idx]
                if alias is not None:
                    continue
            hidden.append(
                f"{class_type} widget_{idx}={val!r} (node {_node_id})"
            )

    return hidden


def _compare_model_values(
    source_snapshot: dict[tuple[str, str], str],
    emitted_snapshot: dict[tuple[str, str], str],
) -> tuple[bool, bool, list[str]]:
    """Compare source and emitted model-value snapshots.

    Returns `(changed, dropped, diffs)`.
    """
    diffs: list[str] = []
    changed = False
    dropped = False

    source_by_value: dict[str, set[tuple[str, str]]] = {}
    for (nid, key), val in source_snapshot.items():
        source_by_value.setdefault(val, set()).add((nid, key))

    emitted_by_value: dict[str, set[tuple[str, str]]] = {}
    for (nid, key), val in emitted_snapshot.items():
        emitted_by_value.setdefault(val, set()).add((nid, key))

    for val_src, src_keys in source_by_value.items():
        if val_src not in emitted_by_value:
            dropped = True
            for nid, key in sorted(src_keys):
                diffs.append(f"dropped: ({nid}, {key})={val_src!r}")

    for (nid, key), val_src in source_snapshot.items():
        if key in {k for (_, k), _ in emitted_snapshot.items()}:
            for (enid, ekey), evalue in emitted_snapshot.items():
                if ekey == key and enid == nid:
                    if evalue != val_src:
                        changed = True
                        diffs.append(
                            f"changed: ({nid}, {key}) from {val_src!r} to {evalue!r}"
                        )
                    break

    src_vals = sorted(source_snapshot.values())
    emt_vals = sorted(emitted_snapshot.values())
    if src_vals != emt_vals:
        changed = True

    return changed, dropped, diffs


def _run_model_value_comparison(
    validation: PortConvertValidation,
    source_api: dict,
    emitted_api: dict,
    workflow: VibeWorkflow,
    *,
    ready_id: str | None,
) -> None:
    """Populate model-value comparison fields on *validation*.

    Compares across five sources:
    1. source API
    2. emitted API
    3. READY_REQUIREMENTS['models'] (ready templates only)
    4. workflow.requirements.models
    5. READY_METADATA['model_assets']
    """
    class_widget_aliases: dict[str, list[str | None]] = {}
    seen_classes: set[str] = set()
    for node in workflow.nodes.values():
        ct = node.class_type
        if ct in seen_classes:
            continue
        seen_classes.add(ct)
        aliases = getattr(node, "metadata", {}).get("input_aliases")
        if isinstance(aliases, (list, tuple)) and aliases:
            class_widget_aliases[ct] = list(aliases)

    src_snapshot = snapshot_model_values(source_api)
    emit_snapshot = snapshot_model_values(emitted_api)
    validation.source_model_snapshot = {
        f"{nid}:{key}": val for (nid, key), val in src_snapshot.items()
    }
    validation.emitted_model_snapshot = {
        f"{nid}:{key}": val for (nid, key), val in emit_snapshot.items()
    }

    changed, dropped, diffs = _compare_model_values(src_snapshot, emit_snapshot)
    validation.model_value_change = changed
    validation.model_value_dropped = dropped
    validation.model_value_diffs = diffs

    validation.hidden_model_filenames = _detect_hidden_model_filenames(
        source_api, class_widget_aliases,
    )

    if validation.hidden_model_filenames:
        for hfn in validation.hidden_model_filenames:
            validation.emission_diagnostics.append(
                EmissionDiagnostic(
                    code="hidden_model_filename",
                    message=f"Model filename hidden under widget_N key: {hfn}",
                    severity="warning",
                    detail={"hidden": hfn},
                )
            )

    # Compare model-like values across all five sources
    _compare_model_values_across_sources(
        validation,
        src_snapshot,
        emit_snapshot,
        workflow,
        ready_id=ready_id,
    )


def _compare_model_values_across_sources(
    validation: PortConvertValidation,
    src_snapshot: dict[tuple[str, str], str],
    emit_snapshot: dict[tuple[str, str], str],
    workflow: VibeWorkflow,
    *,
    ready_id: str | None,
) -> None:
    """Cross-compare model-like values across all five required sources.

    Sources:
    1. source API (src_snapshot)
    2. emitted API (emit_snapshot)
    3. READY_REQUIREMENTS['models'] (ready templates only)
    4. workflow.requirements.models
    5. READY_METADATA['model_assets']
    """
    src_model_vals: set[str] = set(src_snapshot.values())
    emit_model_vals: set[str] = set(emit_snapshot.values())

    # Source 3: READY_REQUIREMENTS['models']
    ready_req_models: set[str] = set()
    if ready_id is not None:
        reqs = _ready_requirements(workflow)
        ready_req_models = _model_names_from_sequence(reqs.get("models", []))

    # Source 4: workflow.requirements.models
    wf_req_models = _model_names_from_sequence(workflow.requirements.models)

    # Source 5: READY_METADATA['model_assets']
    model_assets = workflow.metadata.get("model_assets") or []
    meta_models = _model_names_from_sequence(model_assets if isinstance(model_assets, list) else [])

    validation.ready_requirements_model_snapshot = sorted(ready_req_models)
    validation.workflow_requirements_model_snapshot = sorted(wf_req_models)
    validation.metadata_model_snapshot = sorted(meta_models)

    all_ref_models = ready_req_models | wf_req_models | meta_models

    for model_name in sorted(all_ref_models):
        in_src = model_name in src_model_vals
        in_emit = model_name in emit_model_vals

        if in_src and not in_emit:
            validation.model_value_change = True
            validation.model_value_dropped = True
            validation.model_value_diffs.append(
                f"dropped reference model: {model_name!r} present in source API but missing from emitted API"
            )
            validation.emission_diagnostics.append(
                EmissionDiagnostic(
                    code="hidden_model_filename",
                    message=(
                        f"Model {model_name!r} found in source API, requirements, or metadata "
                        f"but missing from emitted API - may have been dropped during aliasing."
                    ),
                    severity="warning",
                    detail={
                        "model": model_name,
                        "in_source_api": True,
                        "in_emitted_api": False,
                        "in_ready_requirements": model_name in ready_req_models,
                        "in_workflow_requirements": model_name in wf_req_models,
                        "in_metadata_assets": model_name in meta_models,
                    },
                )
            )
        elif not in_src and not in_emit:
            if _looks_like_model_value(model_name):
                validation.model_value_diffs.append(
                    f"reference-only model: {model_name!r} not found in source or emitted API inputs"
                )
                validation.emission_diagnostics.append(
                    EmissionDiagnostic(
                        code="hidden_model_filename",
                        message=(
                            f"Model {model_name!r} referenced in requirements/metadata "
                            f"but not found in source or emitted API inputs."
                        ),
                        severity="warning",
                        detail={
                            "model": model_name,
                            "in_source_api": False,
                            "in_emitted_api": False,
                            "in_ready_requirements": model_name in ready_req_models,
                            "in_workflow_requirements": model_name in wf_req_models,
                            "in_metadata_assets": model_name in meta_models,
                        },
                    )
                )
        elif not in_src and in_emit:
            validation.model_value_change = True
            validation.model_value_diffs.append(
                f"emitted-only reference model: {model_name!r} missing from source API"
            )


def _model_names_from_sequence(values: Any) -> set[str]:
    names: set[str] = set()
    for value in values if isinstance(values, list) else []:
        if isinstance(value, dict):
            name = value.get("name") or value.get("filename") or value.get("file")
        elif isinstance(value, str):
            name = value
        else:
            continue
        if isinstance(name, str) and name:
            names.add(name)
    return names


__all__ = [
    "ConversionWriteError",
    "ManualTemplateRefusal",
    "PortConvertResult",
    "PortConvertValidation",
    "_check_manual_refusal",
    "_looks_like_model_value",
    "port_convert_and_write",
    "port_convert_workflow",
    "snapshot_model_values",
    "validate_emitted_module",
]
