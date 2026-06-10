from __future__ import annotations

import argparse
import json
from typing import Any

from vibecomfy.porting.workbench import analyze_source

from ._shared import (
    _attach_contract_fields,
    _attach_report_strict_ready,
    _emit_strict_ready_load_failure,
    _inject_schema_source_metadata,
    _render_check,
)


def _cmd_port_check(args: argparse.Namespace) -> int:
    try:
        payload, report = build_port_check_payload(args)
    except Exception as exc:
        return _emit_strict_ready_load_failure(
            args,
            exc,
            operation="check",
            strict_enabled=getattr(args, "strict_ready_template", False),
        )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_check(report))
    return 1 if report.has_errors else 0


def build_port_check_payload(args: argparse.Namespace) -> tuple[dict[str, Any], Any]:
    from vibecomfy.commands import port as _port

    schema_provider = _port._build_authoring_provider(args)
    setattr(args, "_schema_provider_name", type(schema_provider).__name__)
    port_mode: str = "strict_ready" if getattr(args, "strict_ready_template", False) else "auto"
    report = analyze_source(
        args.workflow,
        schema_provider=schema_provider,
        head_check_models=args.head_check_models,
        mode=port_mode,
    )
    if getattr(args, "strict_ready_template", False):
        _port._apply_strict_ready_template_gate(report)
    _inject_schema_source_metadata(report, args)
    payload = report.to_json()
    _attach_contract_fields(payload)
    _attach_report_strict_ready(payload)
    return payload, report
