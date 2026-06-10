from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from vibecomfy.porting.lint import lint_ready_template
from vibecomfy.utils import find_repo_root


def _cmd_port_lint(args: argparse.Namespace) -> int:
    """Convention enforcer over generated templates."""
    all_mode = getattr(args, "all", False)
    json_mode = getattr(args, "json", False)

    if all_mode:
        ready_root = find_repo_root() / "ready_templates"
        paths = list(ready_root.rglob("*.py"))
    else:
        wf_path = Path(args.workflow)
        if wf_path.is_file():
            paths = [wf_path]
        else:
            # Try as ready template ID
            ready_root = find_repo_root() / "ready_templates"
            candidate = ready_root / f"{args.workflow}.py"
            if candidate.is_file():
                paths = [candidate]
            else:
                print(f"Workflow not found: {args.workflow}", file=sys.stderr)
                return 1

    all_diags: list[Any] = []
    has_errors = False

    for path in sorted(paths):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        diags = lint_ready_template(source, str(path))
        if json_mode:
            all_diags.extend(
                {
                    "severity": d.severity,
                    "path": d.path,
                    "line": d.line,
                    "code": d.code,
                    "message": d.message,
                    "detail": d.detail,
                }
                for d in diags
            )
        else:
            if diags:
                print(f"{path}:")
                for d in diags:
                    marker = {"error": "error", "warning": "warning", "info": "info"}.get(d.severity, d.severity)
                    print(f"  L{d.line}: {marker}: {d.message}")
                sev_counts = {"error": 0, "warning": 0, "info": 0}
                for d in diags:
                    sev_counts[d.severity] = sev_counts.get(d.severity, 0) + 1
                print(f"  {sev_counts['warning']} warnings, {sev_counts['info']} info, {sev_counts['error']} errors")
                print()
            if any(d.severity == "error" for d in diags):
                has_errors = True

    if json_mode:
        payload = {
            "diagnostics": all_diags,
            "total": len(all_diags),
            "has_errors": has_errors,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if has_errors else 0

    return 1 if has_errors else 0
