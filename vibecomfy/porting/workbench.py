from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

PortAnalysisMode = Literal["auto", "scratchpad", "strict_ready", "app_active"]

from vibecomfy.cli_loader import _ready_id_for
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.environment_diagnostics import metadata_environment_warnings
from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape, normalize_to_api
from vibecomfy.metadata import OUTPUT_NODE_NAMES
from vibecomfy.contracts import build_contract
from vibecomfy.node_packs import resolve_node_packs, unresolved_class_types
from vibecomfy.custom_node_refs import check_pack_pin_compatibility
from vibecomfy.node_packs_lockfile import read_lockfile
from vibecomfy.porting.assets import analyze_model_assets
from vibecomfy.porting.emitter import (
    READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
    READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
    READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE,
    READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
    READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
)
from vibecomfy.porting.report import NodePackSuggestion, PortIssue, PortReport
from vibecomfy.porting.strict_ready import StrictReadyContext, validate_strict_ready_workflow
from vibecomfy.porting.widget_aliases import widget_alias_analysis, widget_names_for_class
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.scratchpad_loader import load_scratchpad
from vibecomfy.schema import schema_for, schema_registry_empty
from vibecomfy.workflow import ValidationIssue, VibeWorkflow


from vibecomfy.contracts.validation import OPAQUE_COMPONENT_CLASS_RE as _OPAQUE_COMPONENT_CLASS_RE  # noqa: E402

_KNOWN_RUNTIME_REQUIRED_INPUTS: dict[str, frozenset[str]] = {
    # VideoHelperSuite validates these at Comfy queue time. Keep this local
    # contract so port checks fail even when object_info/node_index is missing.
    "VHS_VideoCombine": frozenset(
        {
            "filename_prefix",
            "format",
            "frame_rate",
            "images",
            "loop_count",
            "pingpong",
            "save_output",
        }
    ),
    "LTXICLoRALoaderModelOnly": frozenset({"lora_name", "model", "strength_model"}),
    "LTXAddVideoICLoRAGuide": frozenset(
        {
            "crop",
            "frame_idx",
            "image",
            "latent",
            "latent_downscale_factor",
            "negative",
            "positive",
            "strength",
            "tile_overlap",
            "tile_size",
            "use_tiled_encode",
            "vae",
        }
    ),
}

_KNOWN_DYNAMIC_COMBO_SELECTORS: dict[str, frozenset[str]] = {
    "LTXVImgToVideoInplaceKJ": frozenset({"num_images"}),
    "LTXVAddGuideMulti": frozenset({"num_guides"}),
}


@dataclass(slots=True)
class LoadedPortSource:
    source_ref: str
    source_kind: str
    workflow: VibeWorkflow
    raw_workflow: dict[str, Any] | None = None
    source_path: str | None = None
    indexed_id: str | None = None
    source_hash: str | None = None


def analyze_source(
    source: str,
    *,
    schema_provider: Any | None = None,
    head_check_models: bool = False,
    head_client: Any | None = None,
    mode: PortAnalysisMode = "auto",
) -> PortReport:
    loaded = load_port_source(source, schema_provider=schema_provider)
    workflow = loaded.workflow
    resolved_mode = _resolve_analysis_mode(mode, workflow)

    api_prompt: dict[str, Any] | None = None
    compile_issue: PortIssue | None = None
    try:
        api_prompt = workflow.compile("api")
    except Exception as exc:
        compile_issue = PortIssue(
            code="api_compile_failed",
            message=f"API compile failed: {type(exc).__name__}: {exc}",
            severity="error",
            detail={"source": source},
            recommendation="Fix graph structure before running validation or conversion.",
        )

    report = PortReport(
        source=source,
        provenance=_provenance(loaded),
        source_hash=loaded.source_hash,
        workflow_id=workflow.id,
        workflow_shape=_workflow_shape(workflow),
        node_counts=dict(sorted(Counter(node.class_type for node in workflow.nodes.values()).items())),
        output_mode="analysis",
        recommendations=_recommendations(source, loaded),
        metadata={
            "source_kind": loaded.source_kind,
            "source_path": loaded.source_path,
            "runtime_class_types": workflow.runtime_class_types(),
        },
    )
    report.metadata["contract"] = build_contract(workflow).to_dict()

    for issue in workflow.helper_diagnostics():
        report.diagnostics.append(_port_issue_from_validation(issue, category="helper"))

    report.diagnostics.extend(_materialization_diagnostics(workflow, resolved_mode=resolved_mode))
    report.diagnostics.extend(_save_output_mapping_diagnostics(workflow, source_kind=loaded.source_kind))

    custom_node_analysis = _custom_node_analysis(workflow, schema_provider=schema_provider)
    report.metadata["custom_node_analysis"] = custom_node_analysis
    report.node_pack_suggestions.extend(custom_node_analysis["suggestions"])
    report.diagnostics.extend(custom_node_analysis["diagnostics"])

    if compile_issue is not None:
        report.diagnostics.append(compile_issue)
    report.diagnostics.extend(_known_runtime_required_input_diagnostics(api_prompt))
    report.diagnostics.extend(_known_dynamic_combo_selector_diagnostics(api_prompt))
    report.diagnostics.extend(
        _known_runtime_compatibility_diagnostics(api_prompt, metadata=workflow.metadata)
    )
    report.diagnostics.extend(_metadata_environment_diagnostics(workflow.metadata))

    asset_analysis = analyze_model_assets(
        raw_workflow=loaded.raw_workflow,
        api_prompt=api_prompt,
        scratchpad_path=loaded.source_path if loaded.source_kind == "scratchpad" and loaded.source_path else None,
        ready_metadata=workflow.metadata,
        ready_requirements={
            "models": workflow.metadata.get("model_assets", workflow.requirements.models),
            "custom_nodes": workflow.requirements.custom_nodes,
        },
        head_check=head_check_models,
        head_client=head_client,
    )
    report.asset_candidates.extend(asset_analysis.candidates)
    report.asset_checks.extend(asset_analysis.checks)
    report.diagnostics.extend(asset_analysis.diagnostics)

    widget_analysis = _widget_analysis(api_prompt, raw_workflow=loaded.raw_workflow, schema_provider=schema_provider)
    report.metadata["widget_analysis"] = widget_analysis
    for alias in widget_analysis["unresolved_widget_aliases"]:
        report.diagnostics.append(
            PortIssue(
                code="widget_alias_unresolved",
                message=f"Input {alias['input']!r} on node {alias['node_id']} remains positional.",
                severity="warning",
                node_id=alias["node_id"],
                class_type=alias["class_type"],
                detail=alias,
                recommendation="Compare against object_info/widget schema before materializing a ready template.",
            )
        )
    for missing in widget_analysis["missing_compiled_widget_inputs"]:
        report.diagnostics.append(
            PortIssue(
                code="compiled_widget_input_missing",
                message=(
                    f"Node {missing['node_id']} ({missing['class_type']}) has positional widget "
                    f"{missing['widget_key']} but compiled API is missing required input {missing['expected_input']!r}."
                ),
                severity="error",
                node_id=missing["node_id"],
                class_type=missing["class_type"],
                detail=missing,
                recommendation="Add the class to compile-time widget aliasing or update the widget schema before RunPod validation.",
            )
        )

    validation_report = workflow.validate(schema_provider=schema_provider) if schema_provider is not None else workflow.validate()
    report.metadata["schema_validation"] = {
        "schema_provider": schema_provider is not None,
        "ok": validation_report.ok,
        "issue_count": len(validation_report.issues),
    }
    for issue in validation_report.issues:
        report.diagnostics.append(_port_issue_from_validation(issue, category="schema"))

    # -- readability diagnostics --------------------------------------
    report.diagnostics.extend(_readability_diagnostics(workflow, api_prompt=api_prompt))
    # -- strict-template style diagnostics ---------------------------
    report.diagnostics.extend(_strict_template_style_diagnostics(loaded))
    if resolved_mode in {"strict_ready", "app_active"}:
        strict_diagnostics = validate_strict_ready_workflow(
            workflow,
            StrictReadyContext(
                ready_id=loaded.indexed_id or workflow.metadata.get("ready_template") or workflow.id,
                source_path=loaded.source_path,
                mode=resolved_mode,
                is_post_resolution=False,
            ),
            api_prompt=api_prompt,
            widget_analysis=widget_analysis,
        )
        report.diagnostics = _dedupe_strict_ready_diagnostics(
            [*report.diagnostics, *strict_diagnostics]
        )
        report.metadata["strict_ready"] = {
            "ok": not any(issue.severity == "error" for issue in strict_diagnostics),
            "diagnostic_count": len(strict_diagnostics),
            "error_count": sum(1 for issue in strict_diagnostics if issue.severity == "error"),
        }

    if report.asset_candidates:
        report.recommendations.append(f"Review model assets before RunPod validation; use `vibecomfy fetch {source} --dry-run` for URL-backed assets.")
    if any(issue.severity == "error" for issue in report.diagnostics):
        report.recommendations.append("Resolve error diagnostics before spending RunPod GPU time.")

    return report


def _metadata_environment_diagnostics(metadata: dict[str, Any]) -> list[PortIssue]:
    return [
        PortIssue(
            code="metadata_environment_warning",
            message=warning,
            severity="warning",
            detail={"category": "environment"},
            recommendation="Review READY_METADATA hardware/python_env before launching an ensured or GPU-backed run.",
        )
        for warning in metadata_environment_warnings(metadata)
    ]


def _dedupe_strict_ready_diagnostics(diagnostics: list[PortIssue]) -> list[PortIssue]:
    by_key: dict[tuple[str, str], PortIssue] = {}
    for issue in diagnostics:
        key = (issue.code, str((issue.detail or {}).get("target") or issue.node_id or ""))
        existing = by_key.get(key)
        if existing is None or _severity_rank(issue.severity) > _severity_rank(existing.severity):
            by_key[key] = issue
    return sorted(
        by_key.values(),
        key=lambda issue: (
            _severity_rank(issue.severity) * -1,
            issue.code,
            str((issue.detail or {}).get("target") or issue.node_id or ""),
        ),
    )


def _severity_rank(severity: str) -> int:
    return {"info": 0, "warning": 1, "error": 2}.get(severity, 1)


def _resolve_analysis_mode(
    mode: PortAnalysisMode,
    workflow: VibeWorkflow,
) -> PortAnalysisMode:
    """Resolve ``mode=\"auto\"`` to the concrete analysis mode.

    When ``mode`` is ``\"auto\"``, the workflow metadata is inspected:
    ``app_active`` is True or ``coverage_tier == \"required\"`` selects
    ``app_active``; otherwise ``scratchpad`` is returned.

    Explicit modes (``scratchpad``, ``strict_ready``, ``app_active``) are
    returned unchanged.
    """
    if mode != "auto":
        return mode
    metadata = workflow.metadata or {}
    if metadata.get("app_active") is True:
        return "app_active"
    if metadata.get("coverage_tier") == "required":
        return "app_active"
    return "scratchpad"


def _materialization_diagnostics(
    workflow: VibeWorkflow,
    *,
    resolved_mode: PortAnalysisMode = "scratchpad",
) -> list[PortIssue]:
    issues: list[PortIssue] = []
    for node in workflow.nodes.values():
        class_type = str(node.class_type)
        if class_type == "None":
            issues.append(
                PortIssue(
                    code="unmaterialized_node_class",
                    message=(
                        f"Node {node.id} has class_type 'None'; the workflow was converted without a real "
                        "runtime node class for this operation."
                    ),
                    severity="error",
                    node_id=node.id,
                    class_type=class_type,
                    detail={"category": "materialization", "analysis_mode": resolved_mode},
                    recommendation=(
                        "Re-export with all custom/core nodes available, or replace this source with a fully "
                        "materialized API workflow before conversion or RunPod validation."
                    ),
                )
            )
        elif _OPAQUE_COMPONENT_CLASS_RE.match(class_type):
            # Opaque component classes (UUID class types) are a warning in
            # scratchpad mode but a hard error in strict_ready/app_active.
            opaque_severity: Literal["error", "warning"] = (
                "warning" if resolved_mode == "scratchpad" else "error"
            )
            opaque_recommendation: str
            if resolved_mode == "scratchpad":
                opaque_recommendation = (
                    "Opaque component node will block promotion to a ready template. "
                    "Replace with a known first-class replacement node and declared "
                    "inputs/outputs/requirements before using --ready-id."
                )
            else:
                opaque_recommendation = (
                    "Inline component/subgraph definitions with graphbuilder or ComfyUI's converter before "
                    "materializing a ready template. Do not wrap an opaque UUID runtime node in a Python "
                    "name; promotion requires real workflow-builder code with a known first-class replacement node."
                )
            issues.append(
                PortIssue(
                    code="opaque_component_node_class",
                    message=(
                        f"Node {node.id} uses opaque component class {class_type!r}; headless API execution "
                        "will not know this class unless the component is inlined."
                    ),
                    severity=opaque_severity,
                    node_id=node.id,
                    class_type=class_type,
                    detail={
                        "category": "materialization",
                        "analysis_mode": resolved_mode,
                    },
                    recommendation=opaque_recommendation,
                )
            )
    return issues


def _known_runtime_required_input_diagnostics(api_prompt: dict[str, Any] | None) -> list[PortIssue]:
    if api_prompt is None:
        return []

    issues: list[PortIssue] = []
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        required_inputs = _KNOWN_RUNTIME_REQUIRED_INPUTS.get(class_type)
        if not required_inputs:
            continue
        inputs = node.get("inputs")
        provided = set(inputs) if isinstance(inputs, dict) else set()
        for input_name in sorted(required_inputs - provided):
            issues.append(
                PortIssue(
                    code="known_runtime_required_input_missing",
                    message=(
                        f"Node {node_id} ({class_type}) is missing runtime-required input "
                        f"{input_name!r}; Comfy will reject this prompt at queue time."
                    ),
                    severity="error",
                    node_id=str(node_id),
                    class_type=class_type,
                    detail={
                        "category": "runtime_contract",
                        "input": input_name,
                        "source": "committed_runtime_required_inputs",
                    },
                    recommendation="Materialize the input explicitly in the Python workflow before RunPod validation.",
                )
            )
    return issues


def _known_dynamic_combo_selector_diagnostics(api_prompt: dict[str, Any] | None) -> list[PortIssue]:
    if api_prompt is None:
        return []

    issues: list[PortIssue] = []
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        selectors = _KNOWN_DYNAMIC_COMBO_SELECTORS.get(class_type)
        if not selectors:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}
        for selector in sorted(selectors):
            dotted_inputs = sorted(name for name in inputs if name.startswith(f"{selector}."))
            if not dotted_inputs or selector in inputs:
                continue
            issues.append(
                PortIssue(
                    code="dynamic_combo_selector_missing",
                    message=(
                        f"Node {node_id} ({class_type}) has dynamic inputs for {selector!r} "
                        "but is missing the selector input; Comfy will pass flat dotted inputs at execution."
                    ),
                    severity="error",
                    node_id=str(node_id),
                    class_type=class_type,
                    detail={
                        "category": "runtime_contract",
                        "selector": selector,
                        "dotted_inputs": dotted_inputs,
                        "source": "committed_dynamic_combo_contract",
                    },
                    recommendation=(
                        f"Materialize {selector!r} with the selected option count alongside the "
                        f"{selector}.* dynamic inputs."
                    ),
                )
            )
    return issues


def _known_runtime_compatibility_diagnostics(
    api_prompt: dict[str, Any] | None, *, metadata: dict[str, Any] | None = None
) -> list[PortIssue]:
    if api_prompt is None:
        return []

    runtime_packages = (metadata or {}).get("runtime_packages") or []
    declares_sageattention = any(
        isinstance(package, dict) and package.get("name") == "sageattention"
        for package in runtime_packages
    )
    issues: list[PortIssue] = []
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if class_type == "LTX2MemoryEfficientSageAttentionPatch":
            if declares_sageattention:
                continue
            issues.append(
                PortIssue(
                    code="optional_acceleration_requires_unavailable_package",
                    message=(
                        f"Node {node_id} (LTX2MemoryEfficientSageAttentionPatch) requires a "
                        "sageattention-capable CUDA environment; the standard RunPod image does not "
                        "provide that contract."
                    ),
                    severity="error",
                    node_id=str(node_id),
                    class_type="LTX2MemoryEfficientSageAttentionPatch",
                    detail={
                        "category": "runtime_contract",
                        "missing_package": "sageattention",
                        "capability": "ltx2_memory_efficient_sage_attention",
                    },
                    recommendation=(
                        "Remove this patch for portable 4090 RunPod validation, or declare and "
                        "install a sageattention-capable environment explicitly."
                    ),
                )
            )
            continue
        if class_type == "LTX2SamplingPreviewOverride":
            issues.append(
                PortIssue(
                    code="headless_preview_override_not_supported",
                    message=(
                        f"Node {node_id} (LTX2SamplingPreviewOverride) installs a live preview callback "
                        "that depends on ComfyUI frontend server state; headless RunPod execution can crash "
                        "when that state is absent."
                    ),
                    severity="error",
                    node_id=str(node_id),
                    class_type="LTX2SamplingPreviewOverride",
                    detail={
                        "category": "runtime_contract",
                        "capability": "ltx2_live_sampling_preview",
                    },
                    recommendation=(
                        "Remove this preview override for headless validation and route the model directly "
                        "to the downstream sampling/NAG nodes."
                    ),
                )
            )
            continue
        if class_type != "PathchSageAttentionKJ":
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        sage_attention = inputs.get("sage_attention", inputs.get("widget_0"))
        if sage_attention in {None, "disabled"}:
            continue
        if declares_sageattention:
            continue
        issues.append(
            PortIssue(
                code="optional_acceleration_requires_unavailable_package",
                message=(
                    f"Node {node_id} (PathchSageAttentionKJ) enables sageattention mode "
                    f"{sage_attention!r}; the standard RunPod image does not install sageattention."
                ),
                severity="error",
                node_id=str(node_id),
                class_type="PathchSageAttentionKJ",
                detail={
                    "category": "runtime_contract",
                    "input": "sage_attention",
                    "value": sage_attention,
                    "missing_package": "sageattention",
                },
                recommendation="Set sage_attention to 'disabled' for portable 4090 RunPod validation.",
            )
        )
    return issues


def _save_output_mapping_diagnostics(workflow: VibeWorkflow, *, source_kind: str) -> list[PortIssue]:
    if source_kind not in {"ready", "scratchpad"}:
        return []
    output_directory = _configured_output_directory(workflow)
    if output_directory is None:
        return []

    output_root = Path(output_directory).expanduser().resolve()
    issues: list[PortIssue] = []
    for node in workflow.runtime_nodes().values():
        if node.class_type not in OUTPUT_NODE_NAMES:
            continue
        values = {**node.widgets, **node.inputs}
        prefix = values.get("filename_prefix", values.get("widget_0"))
        if isinstance(prefix, str):
            issue = _save_prefix_mapping_issue(node.id, node.class_type, prefix, output_root)
            if issue is not None:
                issues.append(issue)
        for field in ("output_directory", "output_dir", "output_path", "save_path", "folder", "folder_path"):
            value = values.get(field)
            if isinstance(value, str):
                issue = _absolute_save_path_mapping_issue(node.id, node.class_type, field, value, output_root)
                if issue is not None:
                    issues.append(issue)
    return issues


def _save_prefix_mapping_issue(
    node_id: str,
    class_type: str,
    prefix: str,
    output_root: Path,
) -> PortIssue | None:
    path = Path(prefix).expanduser()
    if not path.is_absolute() and ".." not in path.parts:
        return None
    candidate = path if path.is_absolute() else output_root / path
    if _is_relative_to(candidate.resolve(), output_root):
        return None
    return PortIssue(
        code="save_output_path_outside_output_directory",
        message=(
            f"Save node {node_id} uses filename_prefix {prefix!r}, which resolves outside configured "
            f"output_directory {str(output_root)!r}."
        ),
        severity="warning",
        node_id=node_id,
        class_type=class_type,
        detail={
            "category": "outputs",
            "field": "filename_prefix",
            "value": prefix,
            "output_directory": str(output_root),
        },
        recommendation="Use a relative filename_prefix under output_directory so run metadata can map Comfy outputs to artifacts.",
    )


def _absolute_save_path_mapping_issue(
    node_id: str,
    class_type: str,
    field: str,
    value: str,
    output_root: Path,
) -> PortIssue | None:
    path = Path(value).expanduser()
    if not path.is_absolute():
        return None
    if _is_relative_to(path.resolve(), output_root):
        return None
    return PortIssue(
        code="save_output_path_outside_output_directory",
        message=(
            f"Save node {node_id} sets {field}={value!r}, which is outside configured "
            f"output_directory {str(output_root)!r}."
        ),
        severity="warning",
        node_id=node_id,
        class_type=class_type,
        detail={
            "category": "outputs",
            "field": field,
            "value": value,
            "output_directory": str(output_root),
        },
        recommendation="Save artifacts under the configured output_directory or mirror that path in comfy_configuration.",
    )


def _configured_output_directory(workflow: VibeWorkflow) -> str | None:
    values: dict[str, Any] = {}
    metadata_config = workflow.metadata.get("comfy_configuration")
    if isinstance(metadata_config, dict):
        values.update(metadata_config)
    env_config = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if env_config:
        try:
            parsed = json.loads(env_config)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            values.update(parsed)
    output_directory = values.get("output_directory")
    return str(output_directory) if output_directory else None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _load_workflow_from_image(path: Path) -> dict[str, Any]:
    """Extract an embedded ComfyUI workflow chunk from a PNG/WebP image.

    ComfyUI stores the litegraph/UI workflow JSON in a ``workflow`` metadata
    chunk (with a legacy ``prompt`` API fallback). Returns the parsed dict, which
    the caller feeds through the normal normalize pipeline. Raises an
    ImportError-style message when Pillow is unavailable, and a clear error when
    no embedded chunk is present or the chunk is not valid JSON.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # Pillow is an optional [png] dependency.
        raise ImportError(
            "Reading a workflow embedded in a PNG/WebP image requires Pillow. "
            "Install it with the optional dependency group: "
            "pip install 'vibecomfy[png]'."
        ) from exc

    with Image.open(path) as img:
        meta: dict[str, Any] = {}
        text = getattr(img, "text", None)
        if isinstance(text, dict):
            meta.update(text)
        info = getattr(img, "info", None)
        if isinstance(info, dict):
            for key, value in info.items():
                meta.setdefault(key, value)
        raw_chunk = meta.get("workflow")
        if raw_chunk is None:
            raw_chunk = meta.get("prompt")

    if raw_chunk is None:
        raise ValueError(
            f"No embedded ComfyUI workflow found in {path} "
            "(expected a 'workflow' or 'prompt' metadata chunk)."
        )
    if isinstance(raw_chunk, (bytes, bytearray)):
        raw_chunk = raw_chunk.decode("utf-8", errors="replace")
    if isinstance(raw_chunk, dict):
        return raw_chunk
    try:
        data = json.loads(raw_chunk)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(
            f"Embedded workflow chunk in {path} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"Embedded workflow chunk in {path} did not decode to a JSON object."
        )
    return data


def load_port_source(
    source: str,
    *,
    schema_provider: Any | None = None,
    use_comfy_converter: bool = True,
) -> LoadedPortSource:
    ready_id = _ready_id_for(source)
    if ready_id is not None:
        workflow = workflow_from_ready(ready_id)
        path = workflow.source.path
        return LoadedPortSource(
            source_ref=source,
            source_kind="ready",
            workflow=workflow,
            source_path=path,
            indexed_id=ready_id,
            source_hash=_hash_file(path) if path else None,
        )

    source_path = Path(source)
    if source_path.is_file() and source_path.suffix.lower() == ".py":
        workflow = load_scratchpad(source_path, provenance_override="user_confirmed")
        return LoadedPortSource(
            source_ref=source,
            source_kind="scratchpad",
            workflow=workflow,
            source_path=str(source_path),
            source_hash=_hash_file(source_path),
        )

    resolved_path: str | None = None
    indexed_id: str | None = None
    try:
        resolved_path = resolve_workflow_path(source)
        if source != resolved_path:
            indexed_id = source
    except FileNotFoundError:
        if source_path.is_file():
            resolved_path = str(source_path)
        else:
            raise

    resolved = Path(resolved_path)
    if resolved.suffix.lower() == ".py":
        workflow = load_scratchpad(resolved, provenance_override="user_confirmed")
        return LoadedPortSource(
            source_ref=source,
            source_kind="scratchpad",
            workflow=workflow,
            source_path=str(resolved),
            indexed_id=indexed_id,
            source_hash=_hash_file(resolved),
        )
    if resolved.suffix.lower() in {".png", ".webp"}:
        raw = _load_workflow_from_image(resolved)
        api = normalize_to_api(
            raw,
            schema_provider=schema_provider,
            use_comfy_converter=use_comfy_converter,
            comfy_converter_strict=True,
        )
        workflow = convert_to_vibe_format(
            api,
            source_path=str(resolved),
            workflow_id=indexed_id or resolved.stem,
            schema_provider=schema_provider,
        )
        return LoadedPortSource(
            source_ref=source,
            source_kind="indexed_json" if indexed_id else "raw_json",
            workflow=workflow,
            raw_workflow=raw,
            source_path=str(resolved),
            indexed_id=indexed_id,
            source_hash=_hash_file(resolved),
        )
    if resolved.suffix.lower() != ".json":
        raise FileNotFoundError(source)

    raw = load_workflow_json(resolved)
    api = normalize_to_api(
        raw,
        schema_provider=schema_provider,
        use_comfy_converter=use_comfy_converter,
        comfy_converter_strict=True,
    )
    workflow = convert_to_vibe_format(
        api,
        source_path=str(resolved),
        workflow_id=indexed_id or resolved.stem,
        schema_provider=schema_provider,
    )
    return LoadedPortSource(
        source_ref=source,
        source_kind="indexed_json" if indexed_id else "raw_json",
        workflow=workflow,
        raw_workflow=raw,
        source_path=str(resolved),
        indexed_id=indexed_id,
        source_hash=_hash_file(resolved),
    )


def _provenance(loaded: LoadedPortSource) -> dict[str, Any]:
    provenance = dict(loaded.workflow.source.provenance)
    provenance.update(
        {
            "source_ref": loaded.source_ref,
            "source_kind": loaded.source_kind,
            "source_path": loaded.source_path,
            "indexed_id": loaded.indexed_id,
            "workflow_source_id": loaded.workflow.source.id,
            "workflow_source_type": loaded.workflow.source.source_type,
        }
    )
    if loaded.raw_workflow is not None:
        provenance["raw_workflow_shape"] = detect_workflow_shape(loaded.raw_workflow)
    return provenance


def _workflow_shape(workflow: VibeWorkflow) -> dict[str, Any]:
    runtime_nodes = workflow.runtime_nodes()
    return {
        "nodes": len(workflow.nodes),
        "runtime_nodes": len(runtime_nodes),
        "helper_nodes": len(workflow.nodes) - len(runtime_nodes),
        "edges": len(workflow.edges),
        "inputs": len(workflow.inputs),
        "outputs": len(workflow.outputs),
    }


def _recommendations(source: str, loaded: LoadedPortSource) -> list[str]:
    return [
        f"Run `vibecomfy validate {source}` after port fixes.",
        f"Run `vibecomfy nodes install-plan {source}` before installing custom nodes.",
        f"Use `vibecomfy port convert {source} --out out/scratchpads/<name>.py` for Python scratchpad materialization.",
    ]


def _port_issue_from_validation(issue: ValidationIssue, *, category: str) -> PortIssue:
    detail = dict(issue.detail)
    node_id = detail.pop("node_id", None)
    class_type = detail.pop("class_type", None)
    return PortIssue(
        code=issue.code,
        message=issue.message,
        severity=issue.severity if issue.severity in {"error", "warning", "info"} else "warning",
        node_id=node_id,
        class_type=class_type,
        detail={"category": category, **detail},
    )


def _custom_node_analysis(workflow: VibeWorkflow, *, schema_provider: Any | None) -> dict[str, Any]:
    runtime_class_types = set(workflow.runtime_class_types())
    helper_class_types_excluded = sorted(
        {node.class_type for node in workflow.nodes.values() if node.id not in workflow.runtime_nodes()}
    )
    if schema_provider is None or schema_registry_empty(schema_provider):
        missing = {class_type for class_type in runtime_class_types if _class_in_known_pack(class_type)}
        unresolved: list[str] = []
        status = "schema_provider_unavailable" if schema_provider is None else "schema_provider_empty"
    else:
        missing = {class_type for class_type in runtime_class_types if schema_for(schema_provider, class_type) is None}
        unresolved = unresolved_class_types(missing)
        status = "analyzed"

    packs = resolve_node_packs(missing)
    suggestions = [
        NodePackSuggestion(
            pack_name=pack.name,
            repo=pack.repo,
            matched_classes=sorted(missing & pack.classes),
            missing_classes=sorted(missing & pack.classes),
            pip_packages=list(pack.pip_packages),
        )
        for pack in packs
    ]
    diagnostics = [
        PortIssue(
            code="unresolved_runtime_class",
            message=_unknown_class_message(class_type),
            severity="error",
            class_type=class_type,
            detail={"category": "custom_nodes", "runtime_class_type": class_type},
            recommendation=_unknown_class_message(class_type),
        )
        for class_type in unresolved
    ]
    diagnostics.extend(
        PortIssue(
            code=issue.code,
            message=issue.message,
            severity=issue.severity,
            class_type=None,
            detail={"category": "custom_nodes", **issue.detail},
            recommendation="Align READY_METADATA requirements.custom_node_refs with custom_nodes.lock before running with ensured packs.",
        )
        for issue in check_pack_pin_compatibility(workflow, read_lockfile())
    )
    return {
        "status": status,
        "runtime_class_types": sorted(runtime_class_types),
        "helper_class_types_excluded": helper_class_types_excluded,
        "missing_runtime_class_types": sorted(missing),
        "unresolved_runtime_class_types": unresolved,
        "suggestions": suggestions,
        "diagnostics": diagnostics,
    }


def _unknown_class_message(class_type: str) -> str:
    return f"unknown class: {class_type}. Run 'nodes lookup {class_type}' to find the providing pack, then 'nodes install <slug>'."


def _class_in_known_pack(class_type: str) -> bool:
    return bool(resolve_node_packs({class_type}))


def _widget_analysis(
    api_prompt: dict[str, Any] | None,
    *,
    raw_workflow: dict[str, Any] | None,
    schema_provider: Any | None,
) -> dict[str, Any]:
    analysis = widget_alias_analysis(api_prompt, raw_workflow=raw_workflow, schema_provider=schema_provider)
    analysis["missing_compiled_widget_inputs"] = _missing_compiled_widget_inputs(
        api_prompt,
        schema_provider=schema_provider,
    )
    return analysis


def _missing_compiled_widget_inputs(
    api_prompt: dict[str, Any] | None,
    *,
    schema_provider: Any | None,
) -> list[dict[str, Any]]:
    if api_prompt is None:
        return []

    missing: list[dict[str, Any]] = []
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        names = widget_names_for_class(class_type)
        if not names:
            continue
        required_inputs = _required_schema_inputs(schema_provider, class_type)
        for index, expected in enumerate(names):
            if expected is None or expected.startswith("unused_"):
                continue
            widget_key = f"widget_{index}"
            if widget_key not in inputs or expected in inputs:
                continue
            if required_inputs is None and not _class_in_known_pack(class_type):
                continue
            if required_inputs is not None and expected not in required_inputs:
                continue
            missing.append(
                {
                    "node_id": str(node_id),
                    "class_type": class_type,
                    "widget_key": widget_key,
                    "expected_input": expected,
                    "widget_value": inputs[widget_key],
                    "schema_required": required_inputs is not None,
                }
            )
    return missing


def _required_schema_inputs(schema_provider: Any | None, class_type: str) -> set[str] | None:
    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return None
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return None
    required: set[str] = set()
    for name, spec in inputs.items():
        if bool(getattr(spec, "required", False)):
            required.add(str(name))
    return required


def _sort_key(value: Any) -> tuple[int, str]:
    try:
        return (int(value), str(value))
    except (TypeError, ValueError):
        return (10**12, str(value))


def _hash_file(path: str | Path) -> str | None:
    try:
        return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


# -- readability diagnostics ---------------------------------------------


def _readability_diagnostics(
    workflow: VibeWorkflow,
    *,
    api_prompt: dict[str, Any] | None = None,
) -> list[PortIssue]:
    """Generate readability diagnostics for port check reports.

    Reuses the readability warning codes from `EmissionDiagnostic` to
    surface the same issues that the emitter would flag during conversion,
    but without actually running the emitter.  This lets `port check`
    warn about avoidable positional outputs, unresolved widget aliases, and
    hidden model filenames before conversion.
    """
    issues: list[PortIssue] = []

    # ---- output-name diagnostics -------------------------------------------
    for node in workflow.nodes.values():
        nid = str(node.id)
        ctype = str(node.class_type)
        metadata = getattr(node, "metadata", {}) or {}
        output_names = metadata.get("output_names")

        if not isinstance(output_names, (list, tuple)) or not output_names:
            continue

        # Check for duplicates and blanks
        seen: set[str] = set()
        has_duplicate = False
        has_blank = False
        for name in output_names:
            if not isinstance(name, str) or not name:
                has_blank = True
            elif name in seen:
                has_duplicate = True
            else:
                seen.add(name)

        if has_duplicate:
            issues.append(
                PortIssue(
                    code=READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
                    message=(
                        f"Node {nid} ({ctype}) has duplicate output names; "
                        f"emitter will fall back to numeric .out(n)."
                    ),
                    severity="warning",
                    node_id=nid,
                    class_type=ctype,
                    detail={"output_names": list(output_names), "category": "readability"},
                    recommendation="Make output names unique in the source schema before conversion.",
                )
            )
        elif has_blank:
            issues.append(
                PortIssue(
                    code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
                    message=(
                        f"Node {nid} ({ctype}) has partial/blank output names; "
                        f"some outputs will use numeric .out(n)."
                    ),
                    severity="warning",
                    node_id=nid,
                    class_type=ctype,
                    detail={"output_names": list(output_names), "category": "readability"},
                    recommendation="Fill in missing output names in the source schema before conversion.",
                )
            )

    # ---- widget-alias diagnostics ------------------------------------------
    for node in workflow.nodes.values():
        nid = str(node.id)
        ctype = str(node.class_type)
        metadata = getattr(node, "metadata", {}) or {}
        input_aliases = metadata.get("input_aliases")

        # Collect widget_N keys on this node
        widget_keys: set[str] = set()
        for key in list(getattr(node, "widgets", {}).keys()) + list(getattr(node, "inputs", {}).keys()):
            if key.startswith("widget_"):
                widget_keys.add(key)

        if not widget_keys:
            continue

        if isinstance(input_aliases, (list, tuple)) and input_aliases:
            # Check for widget_N indices outside the aliases range
            widget_indices: list[int] = []
            for k in widget_keys:
                try:
                    widget_indices.append(int(k.split("_", 1)[1]))
                except ValueError:
                    pass
            if widget_indices:
                max_idx = max(widget_indices)
                if max_idx >= len(input_aliases):
                    unresolved = sorted(
                        f"widget_{i}" for i in widget_indices
                        if i >= len(input_aliases)
                    )
                    issues.append(
                        PortIssue(
                            code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                            message=(
                                f"Node {nid} ({ctype}) has {len(unresolved)} widget_N key(s) "
                                f"({', '.join(unresolved)}) outside input_aliases range "
                                f"(len={len(input_aliases)}); keeping positional."
                            ),
                            severity="warning",
                            node_id=nid,
                            class_type=ctype,
                            detail={
                                "unresolved_widgets": unresolved,
                                "input_aliases_length": len(input_aliases),
                                "category": "readability",
                            },
                            recommendation="Update the schema to include aliases for all widget inputs.",
                        )
                    )
        else:
            # No input_aliases available - count all widget_N as unresolved
            issues.append(
                PortIssue(
                    code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                    message=(
                        f"Node {nid} ({ctype}) has {len(widget_keys)} unresolved widget_N "
                        f"key(s) ({', '.join(sorted(widget_keys))}) - no schema aliases available."
                    ),
                    severity="warning",
                    node_id=nid,
                    class_type=ctype,
                    detail={
                        "widget_keys": sorted(widget_keys),
                        "category": "readability",
                    },
                    recommendation="Add the class to the widget schema or provide schema-source evidence.",
                )
            )

    # ---- hidden model filename diagnostics ---------------------------------
    if api_prompt is not None:
        issues.extend(_hidden_model_filename_diagnostics(api_prompt, workflow))

    return issues


def _hidden_model_filename_diagnostics(
    api_prompt: dict[str, Any],
    workflow: VibeWorkflow,
) -> list[PortIssue]:
    """Detect model filenames hidden under widget_N keys that cannot be aliased."""
    from vibecomfy.porting.convert import _looks_like_model_value

    issues: list[PortIssue] = []

    # Build class_widget_aliases from node metadata
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

    for node_id, node in api_prompt.items():
        if not isinstance(node, dict):
            continue
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

            issues.append(
                PortIssue(
                    code=READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
                    message=(
                        f"Model filename {val!r} hidden under widget_{idx} "
                        f"on node {node_id} ({class_type})."
                    ),
                    severity="warning",
                    node_id=str(node_id),
                    class_type=class_type,
                    detail={
                        "hidden": f"{class_type} widget_{idx}={val!r}",
                        "category": "readability",
                    },
                    recommendation="Ensure model filenames are reachable through named fields after aliasing.",
                )
            )

    return issues


def _strict_template_style_diagnostics(loaded: LoadedPortSource) -> list[PortIssue]:
    """Check strict-ready templates for style issues detectable from source text.

    Currently checks for:
    - ``local_helper_copy_in_strict_template``: warns when a strict-ready
      template source contains a local ``def _node`` copy.
    """
    issues: list[PortIssue] = []

    # Only check ready templates (strict-ready and indexed-ready)
    if loaded.source_kind != "ready":
        return issues

    source_path = loaded.source_path
    if not source_path:
        return issues

    # Read the source file
    try:
        source_text = Path(source_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return issues

    # Check for local _node helper definition
    if "def _node" in source_text:
        issues.append(
            PortIssue(
                code=READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE,
                message=(
                    f"Strict-ready template {loaded.indexed_id or loaded.source_ref!r} "
                    f"contains a local 'def _node' helper. Use shared helpers from "
                    f"vibecomfy.registry.ready_template instead."
                ),
                severity="warning",
                detail={
                    "category": "readability",
                    "file": source_path,
                },
                recommendation=(
                    "Remove the local _node helper and use shared ready_workflow / "
                    "ready_node / finalize_ready_template / bind_input / bind_output "
                    "from vibecomfy.registry.ready_template."
                ),
            )
        )

    return issues


__all__ = [
    "LoadedPortSource",
    "PortAnalysisMode",
    "analyze_source",
    "load_port_source",
]
