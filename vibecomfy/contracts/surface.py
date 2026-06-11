from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibecomfy.contracts.model import build_contract
from vibecomfy.porting.strict_ready import (
    STRICT_READY_COMPILE_FAILED,
    StrictReadyContext,
    validate_strict_ready_workflow,
)
from vibecomfy.porting.widgets.aliases import widget_alias_analysis
from vibecomfy.utils import find_repo_root
from vibecomfy.workflow import VibeWorkflow


CONTRACT_SHAPE = "workflow_runtime_contract.v1.public_descriptors.v2"
TEMPLATE_INDEX_PATH = find_repo_root() / "template_index.json"


def build_contract_surface(
    workflow: VibeWorkflow,
    *,
    contract: dict[str, Any] | None = None,
    include_strict_counts: bool = True,
) -> dict[str, Any]:
    """Return consistent public contract fields for CLI JSON surfaces."""
    contract_payload = contract or build_contract(workflow).to_dict()
    ready_id = _ready_id(workflow, contract_payload)
    index_row = _template_index_row(ready_id) if ready_id else {}
    strict_counts = _strict_ready_counts(workflow, ready_id=ready_id) if include_strict_counts and ready_id else {}
    metadata = contract_payload.get("metadata") or {}
    custom_nodes = contract_payload.get("custom_nodes") or []
    model_assets = contract_payload.get("model_assets") or []
    coverage_tier = index_row.get("coverage_tier") or metadata.get("coverage_tier") or workflow.metadata.get("coverage_tier") or ""
    capability = index_row.get("capability") or metadata.get("capability") or workflow.metadata.get("capability") or ""
    readiness_class = index_row.get("readiness_class") or contract_payload.get("readiness_level") or "unknown"
    source_scope = index_row.get("source_scope")
    indexed = index_row.get("indexed")
    if source_scope is None and ready_id:
        source_scope = "repo" if indexed is True else "dynamic"
    if indexed is None and ready_id:
        indexed = False
    return {
        "contract_shape": contract_payload.get("contract_shape", CONTRACT_SHAPE),
        "public_inputs": contract_payload.get("public_inputs") or [],
        "public_outputs": contract_payload.get("public_outputs") or [],
        "graph_contract": contract_payload.get("graph_contract") or {},
        "readiness_level": contract_payload.get("readiness_level") or "unknown",
        "readiness_class": readiness_class,
        "coverage_tier": coverage_tier,
        "capability": capability,
        "app_active": bool(index_row.get("app_active") is True or coverage_tier == "required"),
        "blocked": bool(index_row.get("blocked") is True or coverage_tier == "blocked"),
        "reference": bool(index_row.get("reference") is True or coverage_tier == "reference"),
        "supplemental": bool(index_row.get("supplemental") is True or coverage_tier == "supplemental"),
        "source_scope": source_scope,
        "indexed": indexed,
        "model_assets": model_assets,
        "model_count": len(model_assets),
        "custom_nodes": custom_nodes,
        "custom_node_count": len(custom_nodes),
        "strict_ready_diagnostic_counts": strict_counts,
    }


def _ready_id(workflow: VibeWorkflow, contract: dict[str, Any]) -> str | None:
    metadata = contract.get("metadata") or {}
    ready_template = metadata.get("ready_template") or workflow.metadata.get("ready_template")
    if isinstance(ready_template, str) and ready_template:
        return ready_template
    source_type = getattr(workflow.source, "source_type", "")
    if source_type == "ready_template":
        return workflow.id
    return None


def _template_index_row(ready_id: str) -> dict[str, Any]:
    if not TEMPLATE_INDEX_PATH.exists():
        return {}
    try:
        payload = json.loads(TEMPLATE_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    templates = payload.get("templates") if isinstance(payload, dict) else None
    if not isinstance(templates, list):
        return {}
    for row in templates:
        if isinstance(row, dict) and row.get("id") == ready_id:
            return row
    return {}


def _strict_ready_counts(workflow: VibeWorkflow, *, ready_id: str | None) -> dict[str, Any]:
    try:
        api_prompt = workflow.compile("api")
    except Exception:
        return {
            "by_severity": {"error": 1, "warning": 0, "info": 0},
            "by_code": {STRICT_READY_COMPILE_FAILED: 1},
        }
    issues = validate_strict_ready_workflow(
        workflow,
        StrictReadyContext(ready_id=ready_id, source_path=workflow.source.path),
        api_prompt=api_prompt,
        widget_analysis=widget_alias_analysis(api_prompt, schema_provider=None),
    )
    by_severity = {"error": 0, "warning": 0, "info": 0}
    by_code: dict[str, int] = {}
    for issue in issues:
        by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
        by_code[issue.code] = by_code.get(issue.code, 0) + 1
    return {
        "by_severity": by_severity,
        "by_code": {key: by_code[key] for key in sorted(by_code)},
    }


__all__ = ["CONTRACT_SHAPE", "build_contract_surface"]
