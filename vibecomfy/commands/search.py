from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

from vibecomfy.schema import ObjectInfoSchemaProvider
from vibecomfy.search import SearchBootstrapError, build_search_corpus, ensure_indexes, search_entries
from vibecomfy.search.aliases import TASK_ALIASES


def _cmd_search(args: argparse.Namespace) -> int:
    try:
        ensure_indexes(auto_sync=args.auto_sync)
    except SearchBootstrapError as exc:
        print(str(exc))
        return 1

    warnings = []
    schema_provider = ObjectInfoSchemaProvider(args.object_info_cache) if args.object_info_cache else None
    entries = build_search_corpus(auto_sync=False, schema_provider=schema_provider, warnings=warnings)
    for warning in warnings:
        print(f"warning: {warning.message}", file=sys.stderr)
    results = search_entries(entries, args.query, task=args.task, limit=args.limit)

    if args.json:
        print(
            json.dumps(
                {
                    "query": args.query,
                    "task": args.task,
                    "results": [
                        {
                            "id": _entry_id(result.entry.path, result.entry.class_type),
                            "score": result.score,
                            "reasons": list(result.reasons),
                            "entry": asdict(result.entry),
                        }
                        for result in results
                    ],
                    "warnings": [asdict(warning) for warning in warnings],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print("id\tclass_type\tpack\tscore\tsource")
    for result in results:
        entry = result.entry
        print(
            "\t".join(
                [
                    _entry_id(entry.path, entry.class_type),
                    entry.class_type,
                    entry.pack or "",
                    str(result.score),
                    entry.source,
                ]
            )
        )
    return 0


def _entry_id(path: str | None, fallback: str) -> str:
    if path:
        return Path(path).stem
    return fallback


def register(subparsers) -> None:
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--task", choices=sorted(TASK_ALIASES))
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--auto-sync", action="store_true")
    search.add_argument(
        "--object-info-cache",
        help="Use a captured ComfyUI /object_info JSON file as the runtime node corpus.",
    )
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=_cmd_search)
