from __future__ import annotations

import argparse
import json
import sys

from vibecomfy.porting.manual_repair import repair_manual_template


def _cmd_port_repair(args: argparse.Namespace) -> int:
    dry_run = not bool(getattr(args, "write", False))
    try:
        result = repair_manual_template(
            args.workflow,
            mode=args.mode,
            dry_run=dry_run,
            write=bool(getattr(args, "write", False)),
            review_out=args.review_out,
        )
    except Exception as exc:
        print(f"port repair failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    payload = result.to_json()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"port repair: {payload['mode']} {'dry-run' if payload['dry_run'] else 'write'} "
            f"for {payload['path']}"
        )
        print(f"findings: {len(payload['findings'])}; edits: {len(payload['edits'])}")
        if payload.get("review_packet"):
            print(f"review packet: {payload['review_packet']}")
    return 0
