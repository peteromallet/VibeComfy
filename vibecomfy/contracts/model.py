from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from vibecomfy.workflow import VibeWorkflow


def _coerce_json_safe(value: Any) -> Any:
    """Naive JSON coercion: Path→str, Enum→value, skip non-serializable objects."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {_coerce_json_safe(k): _coerce_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_coerce_json_safe(item) for item in value]
    # Skip non-serializable objects (dataclass instances, custom objects, etc.)
    return None


def _coerce_dict_values(d: dict[str, Any]) -> dict[str, Any]:
    """Coerce all values in a dict to JSON-safe types."""
    result: dict[str, Any] = {}
    for key, value in d.items():
        coerced = _coerce_json_safe(value)
        if coerced is not None or value is None:
            result[str(key)] = coerced
    return result


@dataclass(slots=True)
class WorkflowRuntimeContract:
    """First-class workflow runtime contract payload (v1).

    Captures what a workflow declares it needs to run: provider/runtime requirements,
    model assets, custom nodes, inputs, outputs, and runtime class types.
    """

    version: int = 1
    workflow_id: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    readiness_level: str = "unknown"
    model_assets: list[dict[str, Any]] = field(default_factory=list)
    custom_nodes: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    contract_shape: str = "workflow_runtime_contract.v1.public_descriptors.v2"
    public_inputs: list[dict[str, Any]] = field(default_factory=list)
    public_outputs: list[dict[str, Any]] = field(default_factory=list)
    graph_contract: dict[str, Any] = field(default_factory=dict)
    runtime_nodes: list[str] = field(default_factory=list)
    runtime_class_types: list[str] = field(default_factory=list)
    runtime_packages: list[dict[str, Any]] = field(default_factory=list)
    comfy_configuration: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if result.get("runtime") is None:
            result.pop("runtime", None)
        return result


def build_contract(workflow: VibeWorkflow) -> WorkflowRuntimeContract:
    """Build a v1 JSON-serializable runtime contract from a VibeWorkflow.

    Derives payload from workflow fields: source, metadata, requirements, inputs,
    outputs, runtime_class_types(), and compile('api'). Falls back to
    requirements.models when metadata['model_assets'] is absent.
    """
    # Model assets: prefer metadata['model_assets'], fall back to requirements.models
    raw_model_assets = workflow.metadata.get("model_assets")
    if raw_model_assets and isinstance(raw_model_assets, list):
        model_assets = [
            _coerce_dict_values(asset) if isinstance(asset, dict) else {"name": str(asset)}
            for asset in raw_model_assets
        ]
    elif workflow.requirements.models:
        model_assets = [
            {"name": str(model_name)} for model_name in workflow.requirements.models
        ]
    elif getattr(workflow.requirements, "runtime", None) is not None:
        model_assets = [dict(item) for item in workflow.requirements.runtime.models]
    else:
        model_assets = []

    # Runtime package declarations are also exposed through the older
    # descriptive contract field for consumers that have not adopted
    # ``requirements.runtime`` yet.
    raw_runtime_packages = workflow.metadata.get("runtime_packages") or []
    runtime_declared = getattr(workflow.requirements, "runtime", None)
    if not raw_runtime_packages and runtime_declared is not None:
        raw_runtime_packages = [
            {"name": name, "constraint": constraint}
            for name, constraint in runtime_declared.packages
        ]
    if isinstance(raw_runtime_packages, list):
        runtime_packages = [
            _coerce_dict_values(pkg) if isinstance(pkg, dict) else {"name": str(pkg)}
            for pkg in raw_runtime_packages
        ]
    else:
        runtime_packages = []

    # Comfy configuration (descriptive, not validated)
    comfy_config = workflow.metadata.get("comfy_configuration")
    if isinstance(comfy_config, dict):
        comfy_configuration = _coerce_dict_values(comfy_config) or {}
    else:
        comfy_configuration = {}

    # Readiness level
    readiness_level = "unknown"
    if workflow.metadata.get("python_policy_applied"):
        readiness_level = "ready"
    elif workflow.metadata.get("ready_template"):
        readiness_level = "ready"

    # Input names
    inputs_list = sorted(workflow.inputs.keys())

    # Outputs
    outputs_list = []
    for output in workflow.outputs:
        out_dict: dict[str, Any] = {"node_id": str(output.node_id), "output_type": output.output_type}
        if output.name:
            out_dict["name"] = output.name
        outputs_list.append(out_dict)

    public_inputs = serialize_public_inputs(workflow)
    declared_custom_nodes = list(workflow.requirements.custom_nodes)
    if runtime_declared is not None:
        declared_custom_nodes.extend(
            str(item.get("name", item.get("slug", "")))
            for item in runtime_declared.custom_nodes
            if item.get("name") or item.get("slug")
        )
    public_outputs = serialize_public_outputs(workflow)
    graph_contract = serialize_graph_contract(workflow)

    # Runtime class types
    runtime_rt = sorted(workflow.runtime_class_types())

    # Runtime node ids
    runtime_nodes_dict = workflow.runtime_nodes()
    runtime_node_ids = sorted(runtime_nodes_dict.keys())

    from vibecomfy.runtime.dependencies import runtime_requirements_from_workflow
    runtime_decl = runtime_requirements_from_workflow(workflow)
    return WorkflowRuntimeContract(
        version=1,
        workflow_id=workflow.id,
        source=_coerce_dict_values(asdict(workflow.source)),
        readiness_level=readiness_level,
        model_assets=model_assets,
        custom_nodes=sorted(set(declared_custom_nodes)),
        inputs=inputs_list,
        outputs=outputs_list,
        public_inputs=public_inputs,
        public_outputs=public_outputs,
        graph_contract=graph_contract,
        runtime_nodes=runtime_node_ids,
        runtime_class_types=runtime_rt,
        runtime_packages=runtime_packages,
        comfy_configuration=comfy_configuration,
        runtime=runtime_decl.to_dict() if runtime_decl is not None else None,
        metadata={
            "ready_template": workflow.metadata.get("ready_template"),
            "capability": workflow.metadata.get("capability"),
            "coverage_tier": workflow.metadata.get("coverage_tier"),
        },
    )


def serialize_public_inputs(workflow: VibeWorkflow) -> list[dict[str, Any]]:
    """Serialize public input descriptors from workflow bindings.

    This is the canonical additive Sprint 4 shape.  The current IR only
    guarantees name, target, and current value; later descriptor fields are read
    opportunistically when present so CLI surfaces do not need parallel schemas.
    """
    descriptors: list[dict[str, Any]] = []
    for name in sorted(workflow.inputs):
        item = workflow.inputs[name]
        descriptor: dict[str, Any] = {
            "name": item.name,
            "target": {"node_id": str(item.node_id), "field": item.field},
            "node_id": str(item.node_id),
            "field": item.field,
            "value": _coerce_json_safe(getattr(item, "value", None)),
            "type": _coerce_json_safe(getattr(item, "type", None)),
            "default": _coerce_json_safe(getattr(item, "default", None)),
            "required": bool(getattr(item, "required", False)),
            "range": _coerce_json_safe(getattr(item, "range", None)),
            "aliases": _string_list(getattr(item, "aliases", [])),
            "media_semantics": _coerce_json_safe(getattr(item, "media_semantics", None)),
        }
        descriptors.append(descriptor)
    return descriptors


def serialize_public_outputs(workflow: VibeWorkflow) -> list[dict[str, Any]]:
    """Serialize pre-run public output contracts from workflow bindings."""
    descriptors: list[dict[str, Any]] = []
    for output in workflow.outputs:
        descriptor: dict[str, Any] = {
            "name": output.name,
            "node_id": str(output.node_id),
            "output_type": output.output_type,
            "artifact_kind": getattr(output, "artifact_kind", None),
            "mime_type": getattr(output, "mime_type", None),
            "filename_prefix": getattr(output, "filename_prefix", None),
            "expected_cardinality": getattr(output, "expected_cardinality", None),
        }
        descriptors.append(descriptor)
    return descriptors


def serialize_graph_contract(workflow: VibeWorkflow) -> dict[str, Any]:
    """Serialize graph-level contract metadata that is not an input/output."""
    runtime_nodes = workflow.runtime_nodes()
    metadata_graph = workflow.metadata.get("graph_contract")
    graph_contract = _coerce_dict_values(metadata_graph) if isinstance(metadata_graph, dict) else {}
    graph_contract.setdefault("runtime_node_count", len(runtime_nodes))
    graph_contract.setdefault("edge_count", len(workflow.edges))
    graph_contract.setdefault("runtime_class_types", sorted(workflow.runtime_class_types()))
    graph_contract.setdefault("schema_sources", _string_list(workflow.metadata.get("schema_sources", [])))
    graph_contract.setdefault("unresolved_widgets", _list_items(workflow.metadata.get("unresolved_widgets", [])))
    graph_contract.setdefault(
        "unresolved_positional_outputs",
        _list_items(workflow.metadata.get("unresolved_positional_outputs", [])),
    )
    named_outputs = sum(1 for output in workflow.outputs if output.name)
    graph_contract.setdefault("named_output_count", named_outputs)
    graph_contract.setdefault("output_count", len(workflow.outputs))
    return graph_contract


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
