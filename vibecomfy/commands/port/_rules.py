from __future__ import annotations

import argparse
import json

from vibecomfy.porting.rules_registry import rules_by_category, to_json as rules_to_json


def _cmd_port_rules(args: argparse.Namespace) -> int:
    """Codemod rule introspection."""
    explain = getattr(args, "explain", False)
    if args.json:
        print(json.dumps(rules_to_json(), indent=2, sort_keys=True))
        return 0

    cat_map = rules_by_category()
    lines = ["The codemod (vibecomfy/porting/emitter.py) applies these rules:"]
    for cat, rules in sorted(cat_map.items()):
        lines.append("")
        lines.append(cat)
        for rule in rules:
            partial = " (partial coverage)" if rule.partial_coverage else ""
            lines.append(f"  {rule.id}: {rule.description}{partial}")
            if explain:
                lines.append(f"    {rule.behavior}")
                if rule.note:
                    lines.append(f"    Note: {rule.note}")

    lines.append("")
    lines.append("(Read vibecomfy/porting/emitter.py for exact implementation.)")
    lines.append("(This registry has partial coverage; some rules may be undocumented.)")
    print("\n".join(lines))
    return 0
