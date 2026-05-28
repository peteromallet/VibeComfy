from __future__ import annotations

import argparse

from vibecomfy.checks import run_checks
from vibecomfy.commands._output import emit


def _cmd_check(args: argparse.Namespace) -> int:
    report = run_checks()
    code = 0 if report.ok else 1
    if args.json:
        emit(report, json=True, text_renderer=_render_check_report)
        return code
    print(_render_check_report(report))
    return code


def _render_check_report(report) -> str:
    lines = [
        f"status: {report.status}",
        f"schema cache classes: {report.schema_cache_class_count}",
        f"pack files: {report.pack_file_count}",
        f"stub packs: {', '.join(report.stub_pack_inventory) or '-'}",
    ]
    for check in report.checks:
        lines.append(f"{check.status}: {check.name}")
    return "\n".join(lines)


def register(subparsers) -> None:
    parser = subparsers.add_parser("check")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=_cmd_check)


__all__ = ["register"]
