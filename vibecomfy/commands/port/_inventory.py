from __future__ import annotations

import argparse
import json

from vibecomfy.porting.readability_inventory import build_readability_inventory


def _cmd_port_inventory(args: argparse.Namespace) -> int:
    """Repo-only readability inventory for checked-in ready templates.

    ``port inventory --ready --json`` emits a deterministic, versioned JSON
    report built from the static ``ready_templates/**/*.py`` glob.  The report
    never consults plugin/cwd/user-global paths.
    """
    inventory = build_readability_inventory()
    if args.json:
        print(json.dumps(inventory.to_json(), indent=2, sort_keys=True))
    else:
        print(_render_inventory(inventory))
    return 0


def _render_inventory(inventory) -> str:
    entries = inventory.entries
    summary = inventory.summary
    flag_count = sum(1 for e in entries if e.missing_source_provenance)

    lines = [
        f"port inventory: {inventory.template_count} checked-in ready templates",
        f"missing source provenance: {flag_count}",
        f"markers: "
        + " ".join(
            f"{k.split('_', 1)[1]}={v}"
            for k, v in sorted(summary.items())
            if k.startswith("marker_")
        ),
    ]
    # Summary counts
    lines.append(
        f"issues: "
        + ", ".join(
            f"{key}={summary.get(key, 0)}"
            for key in [
                "positional_outs_total",
                "widget_n_fields_total",
                "uuid_class_types_total",
                "n_uuid_variables_total",
                "local_node_copies_total",
                "missing_output_contract",
            ]
        )
    )
    lines.append(f"app_active: {summary.get('app_active', 0)}")
    lines.append(f"templates_with_issues: {summary.get('templates_with_issues', 0)}")

    # Flagged entries
    flagged = [e for e in entries if e.missing_source_provenance]
    if flagged:
        lines.append("")
        lines.append("Flagged (no source provenance):")
        for e in flagged[:20]:
            lines.append(f"  {e.ready_id} ({e.marker})")
        if len(flagged) > 20:
            lines.append(f"  ... {len(flagged) - 20} more flagged entries; rerun with --json for full list")

    return "\n".join(lines)
