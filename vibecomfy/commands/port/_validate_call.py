from __future__ import annotations

import argparse
import json
import sys

from vibecomfy.schema import validate_node_call

from ._shared import _build_validate_call_provider


def _cmd_port_validate_call(args: argparse.Namespace) -> int:
    try:
        kwargs = json.loads(args.kwargs)
    except json.JSONDecodeError as exc:
        payload = {
            "status": "error",
            "class_type": args.class_type,
            "ok": False,
            "errors": [
                {
                    "code": "invalid_kwargs_json",
                    "message": str(exc),
                    "input": None,
                    "detail": {"position": exc.pos},
                }
            ],
            "provider": None,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"invalid --kwargs JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(kwargs, dict):
        payload = {
            "status": "error",
            "class_type": args.class_type,
            "ok": False,
            "errors": [
                {
                    "code": "invalid_kwargs_json",
                    "message": "--kwargs must decode to a JSON object",
                    "input": None,
                    "detail": {"decoded_type": type(kwargs).__name__},
                }
            ],
            "provider": None,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("--kwargs must decode to a JSON object", file=sys.stderr)
        return 2
    provider = _build_validate_call_provider(args)
    report = validate_node_call(args.class_type, kwargs, provider=provider)
    payload = report.to_json()
    payload["status"] = "ok" if report.ok else "error"
    payload["provider"] = type(provider).__name__
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if report.ok:
            print("ok")
        else:
            for issue in report.issues:
                print(f"{issue.code}: {issue.message}", file=sys.stderr)
    return 0 if report.ok else 1
