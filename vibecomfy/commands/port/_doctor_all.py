from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from io import StringIO
from typing import Any

from vibecomfy.schema import get_authoring_schema_provider, get_schema_provider
from vibecomfy.commands.nodes import build_nodes_install_plan_payload

from ._check import build_port_check_payload


def _cmd_port_doctor_all(args: argparse.Namespace) -> int:
    if not getattr(args, "json", False):
        print("port doctor-all currently emits machine-readable output; pass --json", file=sys.stderr)
        return 2
    sections = [
        _doctor_all_port_check,
        _doctor_all_nodes_install_plan,
        _doctor_all_validate,
        _doctor_all_doctor,
        _doctor_all_runtime_doctor,
    ]
    started = time.perf_counter()
    results = [section(args) for section in sections]
    findings = [finding for result in results for finding in result.get("findings", [])]
    payload = {
        "status": "ok" if not any(result["status"] == "error" for result in results) else "error",
        "workflow": args.workflow,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "sections": results,
        "summary": {
            "section_count": len(results),
            "ok_sections": sum(1 for result in results if result["status"] == "ok"),
            "warning_sections": sum(1 for result in results if result["status"] == "warning"),
            "error_sections": sum(1 for result in results if result["status"] == "error"),
            "finding_count": len(findings),
        },
        "findings": findings,
        "next_action": _first_next_action(findings) or f"vibecomfy port check {args.workflow} --json",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload["status"] == "error" else 0


def _doctor_all_section(name: str, func) -> dict[str, Any]:
    started = time.perf_counter()
    stdout = StringIO()
    stderr = StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            from vibecomfy.security import GateContext, set_gate_context  # noqa: PLC0415

            token = set_gate_context(GateContext(non_interactive=True, assume_yes=True))
            try:
                payload, exit_code = func()
            finally:
                token.var.reset(token)
        status = "ok" if exit_code == 0 else "error"
        if isinstance(payload, dict) and payload.get("status") == "warning":
            status = "warning"
        return {
            "name": name,
            "status": status,
            "exit_code": exit_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "payload": payload,
            "findings": _normalize_findings(name, payload),
            "stderr": stderr.getvalue(),
            "captured_stdout": stdout.getvalue(),
            "next_action": _payload_next_action(payload),
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "error",
            "exit_code": 1,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "payload": None,
            "findings": [
                {
                    "section": name,
                    "severity": "error",
                    "code": "section_exception",
                    "message": f"{type(exc).__name__}: {exc}",
                    "next_action": None,
                }
            ],
            "stderr": stderr.getvalue(),
            "captured_stdout": stdout.getvalue(),
            "next_action": None,
        }


def _doctor_all_port_check(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        payload, report = build_port_check_payload(
            argparse.Namespace(
                workflow=args.workflow,
                json=True,
                head_check_models=False,
                strict_ready_template=False,
                runtime_object_info=False,
                object_info_cache=getattr(args, "object_info_cache", None),
                no_object_info_cache=False,
                server_url=None,
            )
        )
        return payload, 1 if report.has_errors else 0

    return _doctor_all_section(
        "port_check",
        run,
    )


def _doctor_all_nodes_install_plan(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        import vibecomfy.node_packs_install as node_packs_install
        from vibecomfy.commands import port as _port

        workflow = _port.load_workflow_reference(args.workflow, schema_provider=get_schema_provider("auto"), allow_scratchpad=True, ready=getattr(args, "ready", False))
        missing_classes = node_packs_install.missing_class_types_for_workflow(workflow)
        authoring_provider = get_authoring_schema_provider()
        missing_classes = {
            class_type
            for class_type in missing_classes
            if authoring_provider.get_schema(str(class_type)) is None
        }
        packs, unresolved = node_packs_install.missing_packs_for_workflow(workflow)
        unresolved = [class_type for class_type in unresolved if class_type in missing_classes]
        packs = [pack for pack in packs if missing_classes & pack.classes]
        payload = {
            "status": "ok" if not unresolved else "error",
            **build_nodes_install_plan_payload(
                args.workflow,
                missing_classes,
                packs,
                unresolved,
            ),
        }
        return payload, 1 if unresolved else 0

    return _doctor_all_section("nodes_install_plan", run)


def _doctor_all_validate(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        from vibecomfy.commands.validate import build_validate_payload

        payload = build_validate_payload(args.workflow)
        return payload, 0 if payload.get("status") == "ok" else 1

    return _doctor_all_section("validate", run)


def _doctor_all_doctor(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        from vibecomfy.commands.doctor import _cmd_doctor

        stdout = StringIO()
        stderr = StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = _cmd_doctor(argparse.Namespace(path=args.workflow, json=True, lint=False, allow_drift=False))
        text = stdout.getvalue().strip()
        payload = json.loads(text) if text else {"status": "error", "errors": ["doctor emitted no JSON"]}
        payload["_captured_stderr"] = stderr.getvalue()
        return payload, exit_code

    return _doctor_all_section("doctor", run)


def _doctor_all_runtime_doctor(args: argparse.Namespace) -> dict[str, Any]:
    def run() -> tuple[dict[str, Any], int]:
        from vibecomfy.commands.runtime import build_runtime_doctor_payload

        payload = build_runtime_doctor_payload()
        return payload, 0 if payload.get("status") == "ok" else 1

    return _doctor_all_section("runtime_doctor", run)


def _normalize_findings(section: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    findings: list[dict[str, Any]] = []
    for item in payload.get("diagnostics") or []:
        if isinstance(item, dict):
            findings.append(
                {
                    "section": section,
                    "severity": item.get("severity", "warning"),
                    "code": item.get("code", "diagnostic"),
                    "message": item.get("message", ""),
                    "next_action": item.get("recommendation") or payload.get("recommended_command"),
                }
            )
    for key, severity in (("errors", "error"), ("warnings", "warning"), ("missing_models", "error"), ("nodepack_warnings", "warning")):
        for item in payload.get(key) or []:
            findings.append(
                {
                    "section": section,
                    "severity": severity,
                    "code": key.rstrip("s"),
                    "message": str(item),
                    "next_action": payload.get("recommended_command"),
                }
            )
    for item in payload.get("issues") or []:
        if isinstance(item, dict):
            findings.append(
                {
                    "section": section,
                    "severity": item.get("severity", "error"),
                    "code": item.get("code", "issue"),
                    "message": item.get("message", ""),
                    "next_action": payload.get("recommended_command"),
                }
            )
    return findings


def _payload_next_action(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    return payload.get("recommended_command") or payload.get("next_action")


def _first_next_action(findings: list[dict[str, Any]]) -> str | None:
    for finding in findings:
        action = finding.get("next_action")
        if action:
            return str(action)
    return None
