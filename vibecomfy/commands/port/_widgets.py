from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from vibecomfy.porting.widgets.aliases import widget_alias_analysis
from vibecomfy.porting.workbench import load_port_source


def _cmd_port_widgets(args: argparse.Namespace) -> int:
    from vibecomfy.commands import port as _port

    schema_provider = _port._build_authoring_provider(args)
    setattr(args, "_schema_provider_name", type(schema_provider).__name__)
    try:
        loaded = load_port_source(
            args.workflow,
            schema_provider=schema_provider,
            use_comfy_converter=False,
        )
    except Exception as exc:
        print(f"port widgets failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    api_prompt = loaded.workflow.compile("api")
    widget_analysis = widget_alias_analysis(
        api_prompt,
        raw_workflow=loaded.raw_workflow,
        schema_provider=schema_provider,
    )
    payload = {
        "source": args.workflow,
        "source_hash": loaded.source_hash,
        **widget_analysis,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_widgets(payload))
    return 0


def _render_widgets(payload: dict[str, Any]) -> str:
    unresolved = payload.get("unresolved_widget_aliases") or []
    suggestions = payload.get("suggestions") or []
    lines = [
        f"port widgets: {len(unresolved)} unresolved positional widget alias"
        f"{'' if len(unresolved) == 1 else 'es'}",
        f"source: {payload.get('source')}",
    ]
    if not unresolved:
        return "\n".join(lines)
    for group in suggestions:
        lines.append(f"- {group['class_type']}: {len(group['nodes'])} node(s), source={group['schema_source']}")
        if group.get("python"):
            lines.append(f"  schema: {group['python']}")
        else:
            lines.append("  schema: unavailable from local object_info/node_index")
        for node in group["nodes"][:5]:
            inputs = ", ".join(node["unresolved_inputs"])
            lines.append(f"  node {node['node_id']}: {inputs}")
    return "\n".join(lines)
