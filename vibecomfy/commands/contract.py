from __future__ import annotations

import argparse

from vibecomfy.cli_loader import load_bundle
from vibecomfy.commands._output import emit
from vibecomfy.contracts import build_contract, doctor_contract
from vibecomfy.contracts.surface import build_contract_surface


def _cmd_contract_inspect(args: argparse.Namespace) -> int:
    bundle = load_bundle(args.workflow)
    bundle.require_canonical_authority("contract inspection")
    workflow = bundle.workflow
    contract = build_contract(workflow)
    payload = contract.to_dict()
    payload.update(build_contract_surface(workflow, contract=payload))
    return emit(payload, json=args.json, text_renderer=_render_contract_inspect)


def _render_contract_inspect(payload: dict) -> str:
    lines = [
        f"version: {payload['version']}",
        f"workflow_id: {payload['workflow_id']}",
        f"readiness_level: {payload['readiness_level']}",
        f"model_assets: {len(payload['model_assets'])} entries",
        f"custom_nodes: {', '.join(payload['custom_nodes']) or '-'}",
        f"inputs: {', '.join(payload['inputs']) or '-'}",
        f"outputs: {len(payload['outputs'])} entries",
        f"contract_shape: {payload['contract_shape']}",
        f"public_inputs: {len(payload['public_inputs'])} entries",
        f"public_outputs: {len(payload['public_outputs'])} entries",
        f"runtime_nodes: {len(payload['runtime_nodes'])} entries",
        f"runtime_class_types: {len(payload['runtime_class_types'])} entries",
        f"runtime_packages: {len(payload['runtime_packages'])} entries",
    ]
    return "\n".join(lines)


def _cmd_contract_doctor(args: argparse.Namespace) -> int:
    bundle = load_bundle(args.workflow)
    bundle.require_canonical_authority("contract diagnostics")
    workflow = bundle.workflow
    contract = build_contract(workflow)
    report = doctor_contract(workflow, contract)
    contract_payload = contract.to_dict()
    surface = build_contract_surface(workflow, contract=contract_payload)
    payload = {
        "status": report.status,
        "contract": contract_payload,
        "diagnostics": [
            {
                "code": d.code,
                "severity": d.severity,
                "message": d.message,
                "node_id": d.node_id,
                "class_type": d.class_type,
                "detail": d.detail,
                "recommendation": d.recommendation,
            }
            for d in report.diagnostics
        ],
        **surface,
    }
    exit_code = emit(payload, json=args.json, text_renderer=_render_contract_doctor)
    if report.status == "error":
        return 1
    return exit_code


def _render_contract_doctor(payload: dict) -> str:
    contract = payload.get("contract") or {}
    lines = [f"status: {payload['status']}"]
    if contract:
        lines.append(f"contract_shape: {contract.get('contract_shape', '-')}")
        lines.append(f"public_inputs: {len(contract.get('public_inputs') or [])} entries")
        lines.append(f"public_outputs: {len(contract.get('public_outputs') or [])} entries")
    if payload["diagnostics"]:
        lines.append("diagnostics:")
        for d in payload["diagnostics"]:
            lines.append(
                f"  [{d['severity'].upper()}] {d['code']}: {d['message']}"
            )
    return "\n".join(lines)


def register(subparsers) -> None:
    contract = subparsers.add_parser("contract")
    contract_subs = contract.add_subparsers(dest="contract_command")

    # contract inspect
    inspect = contract_subs.add_parser("inspect")
    inspect.add_argument("workflow")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=_cmd_contract_inspect)

    # contract doctor
    doctor = contract_subs.add_parser("doctor")
    doctor.add_argument("workflow")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_contract_doctor)
