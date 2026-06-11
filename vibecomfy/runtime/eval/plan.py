from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibecomfy.porting.object_info.consume import output_names, output_types
from vibecomfy.porting.workbench import load_port_source
from .preview_types import preview_plan_for_type


SAVE_OR_PREVIEW_CLASSES = {
    "PreviewImage",
    "PreviewAudio",
    "SaveImage",
    "SaveAnimatedWEBP",
    "SaveAudio",
    "SaveVideo",
    "VHS_VideoCombine",
}


@dataclass(frozen=True)
class EvalNodePlan:
    workflow: str
    node_id: str
    dry_run: bool
    execution_mode: str
    queueable: bool
    lookup: dict[str, Any]
    retained_node_ids: list[str]
    dropped_node_ids: list[str]
    skipped_terminal_node_ids: list[str]
    dependencies_run: list[str]
    outputs: dict[str, dict[str, Any]]
    preview_injections: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    truncated_api: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "node_id": self.node_id,
            "dry_run": self.dry_run,
            "execution_mode": self.execution_mode,
            "queueable": self.queueable,
            "lookup": self.lookup,
            "retained_node_ids": self.retained_node_ids,
            "dropped_node_ids": self.dropped_node_ids,
            "skipped_terminal_node_ids": self.skipped_terminal_node_ids,
            "dependencies_run": self.dependencies_run,
            "outputs": self.outputs,
            "preview_injections": list(self.preview_injections),
            "warnings": list(self.warnings),
            "truncated_api": self.truncated_api,
        }


def plan_eval_node(workflow_ref: str, node_id: str, *, dry_run: bool = True) -> EvalNodePlan:
    loaded = load_port_source(workflow_ref)
    workflow = loaded.workflow
    node_key = str(node_id)
    api = workflow.compile("api")
    lookup = workflow.lookup_id(node_key, source_path=loaded.source_path)
    if node_key not in api:
        return EvalNodePlan(
            workflow_ref, node_key, dry_run, "dry_run" if dry_run else "unavailable",
            False, lookup, [], sorted(api, key=_node_sort_key), [], [], {},
            warnings=[{"code": "unknown_node_id", "message": f"Node {node_key} is not present in compiled API."}],
            truncated_api={},
        )

    retained = _upstream_node_ids(api, node_key)
    truncated_api = {nid: api[nid] for nid in sorted(retained, key=_node_sort_key)}
    dropped = sorted(set(api) - retained, key=_node_sort_key)
    skipped_terminal = [
        nid
        for nid in dropped
        if isinstance(api.get(nid), dict) and str(api[nid].get("class_type")) in SAVE_OR_PREVIEW_CLASSES
    ]
    target_class = str(api[node_key].get("class_type"))
    output_payload, injections, warnings = _classify_outputs(api, node_key, target_class)
    queueable = any(item.get("previewable") for item in output_payload.values()) or _is_terminal_output(api[node_key])
    dependencies = [
        _dependency_label(workflow.lookup_id(nid, source_path=loaded.source_path), nid)
        for nid in sorted(retained - {node_key}, key=_node_sort_key)
    ]
    return EvalNodePlan(
        workflow_ref, node_key, dry_run, "dry_run" if dry_run else "planned_only",
        queueable, lookup, sorted(retained, key=_node_sort_key), dropped, skipped_terminal,
        dependencies, output_payload, preview_injections=injections, warnings=warnings, truncated_api=truncated_api,
    )


def _upstream_node_ids(api: dict[str, Any], node_id: str) -> set[str]:
    retained: set[str] = set()

    def visit(nid: str) -> None:
        if nid in retained or nid not in api:
            return
        retained.add(nid)
        node = api.get(nid)
        inputs = node.get("inputs") if isinstance(node, dict) else {}
        if not isinstance(inputs, dict):
            return
        for value in inputs.values():
            for source in _link_sources(value):
                visit(source)

    visit(node_id)
    return retained


def _link_sources(value: Any) -> list[str]:
    if isinstance(value, list) and len(value) >= 2 and isinstance(value[0], str):
        return [value[0]]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_link_sources(item))
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            result.extend(_link_sources(item))
        return result
    return []


def _classify_outputs(
    api: dict[str, Any],
    node_id: str,
    class_type: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    types = output_types(class_type)
    names = output_names(class_type)
    warnings: list[dict[str, Any]] = []
    if not types:
        warnings.append({"code": "missing_output_schema", "message": (
            f"No cached output schema for {class_type}; eval-node can only report node context."
        )})
        return {}, [], warnings
    has_vae = _has_vae_handle(api, node_id)
    outputs: dict[str, dict[str, Any]] = {}
    injections: list[dict[str, Any]] = []
    for index, comfy_type in enumerate(types):
        name = names[index] if index < len(names) and names[index] else f"output_{index}"
        plan = preview_plan_for_type(comfy_type, has_vae=has_vae)
        output = {"slot": index, "comfy_type": comfy_type, "previewable": plan.previewable,
                  "info": "planned_preview" if plan.previewable else "type-only"}
        if plan.reason:
            output["reason"] = plan.reason
        if plan.wrapped_via:
            output["wrapped_via"] = plan.wrapped_via
            injections.append({"slot": name, "slot_index": index, "comfy_type": comfy_type,
                               "wrapped_via": plan.wrapped_via, "source": [node_id, index]})
        outputs[name] = output
    return outputs, injections, warnings


def _has_vae_handle(api: dict[str, Any], node_id: str) -> bool:
    node = api.get(node_id)
    inputs = node.get("inputs") if isinstance(node, dict) else {}
    if not isinstance(inputs, dict):
        return False
    value = inputs.get("vae")
    if isinstance(value, list) and value and isinstance(value[0], str):
        return True
    return any(
        isinstance(candidate, dict) and str(candidate.get("class_type", "")).lower().endswith("vaeloader")
        for candidate in api.values()
    )


def _is_terminal_output(node: dict[str, Any]) -> bool:
    return str(node.get("class_type")) in SAVE_OR_PREVIEW_CLASSES


def _dependency_label(lookup: dict[str, Any], fallback: str) -> str:
    variable = lookup.get("variable")
    return str(variable or fallback)


def _node_sort_key(node_id: str) -> tuple[int, int | str]:
    return (0, int(node_id)) if str(node_id).isdigit() else (1, node_id)


__all__ = ["EvalNodePlan", "plan_eval_node"]
