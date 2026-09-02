from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from vibecomfy.analysis.fields import trace_public_field
from vibecomfy.contracts import build_contract
from vibecomfy.contracts.surface import build_contract_surface
from vibecomfy.commands._output import emit
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.patches.registry import find_applicable
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.schema import get_schema_provider
from vibecomfy.workflow import ValidationReport


from vibecomfy.ingest.normalize import door_nodes
def _status_from_report(report: ValidationReport) -> str:
    # Inspect intentionally exposes validation only as runnable/unsupported status.
    return "runnable" if report.ok else "unsupported"


def _cmd_inspect(args: argparse.Namespace) -> int:
    # --field mode: delegate to trace_public_field
    field_name = getattr(args, "field", None)
    if field_name:
        try:
            loaded = load_port_source(args.workflow, schema_provider=get_schema_provider("local"))
        except Exception as exc:
            print(f"Failed to load workflow: {type(exc).__name__}: {exc}", __import__("sys").stderr)
            return 1
        result = trace_public_field(loaded.workflow, field_name, source_file=loaded.source_path)
        if result.get("error"):
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(f"Error: {result['error']}")
            return 1
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(_render_tracefield(result))
        return 0

    workflow = load_workflow_any(args.workflow)
    shape = "api"
    # Inspect is a read-only/schema-only command.  Never boot a managed
    # ComfyUI server just because one happens to be installed: an occupied
    # default port must not make static inspection nondeterministic.
    schema_provider = get_schema_provider("local")
    report = workflow.validate(schema_provider=schema_provider)
    applicable_patches = [
        {"name": patch.name, "rationale": patch.rationale(workflow)}
        for patch in find_applicable(workflow)
    ]
    contract = build_contract(workflow).to_dict()
    surface = build_contract_surface(workflow, contract=contract)
    payload = {
        "id": workflow.id,
        "shape": shape,
        "nodes": len(workflow.nodes),
        "edges": len(workflow.edges),
        "inputs": sorted(workflow.inputs),
        "outputs": [asdict(output) for output in workflow.outputs],
        "models": workflow.requirements.models,
        "custom_nodes": workflow.requirements.custom_nodes,
        "status": _status_from_report(report),
        "applicable_patches": applicable_patches,
        "contract": contract,
        **surface,
    }
    return emit(payload, json=args.json, text_renderer=_render_inspect)


def _render_inspect(payload: dict) -> str:
    return "\n".join(
        [
            f"id: {payload['id']}",
            f"shape: {payload['shape']}",
            f"nodes: {door_nodes(payload)}",
            f"edges: {payload['edges']}",
            f"inputs: {', '.join(payload['inputs']) or '-'}",
            f"outputs: {', '.join(output['output_type'] for output in payload['outputs']) or '-'}",
            f"public inputs: {len(payload['public_inputs'])}",
            f"public outputs: {len(payload['public_outputs'])}",
            f"models: {payload['models']}",
            f"custom nodes: {payload['custom_nodes']}",
            f"readiness: {payload['readiness_level']}",
            f"status: {payload['status']}",
        ]
    )


def _render_tracefield(result: dict) -> str:
    lines = [f"field: {result['field']}"]
    lines.append("resolution chain (highest priority first):")
    for entry in result.get("resolution_chain", []):
        desc = entry.get("description", "")
        detail = ""
        if "value" in entry:
            v = entry["value"]
            detail = f" = {v!r}" if not isinstance(v, str) or len(str(v)) < 80 else f" = {str(v)[:77]}..."
        if "node_id" in entry:
            detail = f" at node '{entry['node_id']}' ({entry.get('class_type','')}.{entry.get('field','')}){detail}"
        lines.append(f"  {entry['priority']}. {desc}{detail}")
    aliases = result.get("aliases", [])
    if aliases:
        lines.append("aliases (resolve to same node+field):")
        for alias in aliases:
            lines.append(f"  • {alias!r}")
        lines.append(f"  • {result['field']!r} (canonical)")
    bound = result.get("bound_node")
    if bound:
        lines.append(f"bound to: node id={bound['node_id']} ({bound['class_type']}.{bound['field']})")
    return "\n".join(lines)


def register(subparsers) -> None:
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("workflow")
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--field", help="Drill into one PUBLIC_INPUTS field resolution")
    inspect.set_defaults(func=_cmd_inspect)
