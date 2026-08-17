from __future__ import annotations

import argparse

from vibecomfy.commands._output import emit
from vibecomfy.ingest.sources import sync_sources


from vibecomfy.ingest.door_access import door_nodes
def _cmd_sources_sync(args: argparse.Namespace) -> int:
    result = sync_sources(
        official=args.official,
        external=args.external,
        custom_nodes=args.custom_nodes,
    )
    payload = {"official": result.official, "external": result.external, "nodes": result.nodes}
    return emit(
        payload,
        json=args.json,
        text_renderer=lambda data: f"indexed official={data['official']} external={data['external']} nodes={door_nodes(data)}",
    )


def register(subparsers) -> None:
    sources = subparsers.add_parser("sources")
    sources_sub = sources.add_subparsers(dest="subcmd", required=True)
    sync = sources_sub.add_parser("sync")
    sync.add_argument("--official", default="ready_templates/sources/official")
    sync.add_argument("--external", default="ready_templates/sources/custom_nodes")
    sync.add_argument("--custom-nodes", default="custom_nodes")
    sync.add_argument("--json", action="store_true")
    sync.set_defaults(func=_cmd_sources_sync)
