from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibecomfy.cli_loader import load_bundle
from vibecomfy.schema import get_schema_provider


async def _run(args: argparse.Namespace) -> int:
    provider = get_schema_provider("local")
    first_bundle = load_bundle(
        args.first,
        schema_provider=provider,
    )
    second_ref = args.second or args.first
    second_bundle = load_bundle(
        second_ref,
        schema_provider=provider,
    )
    _first_record = first_bundle.compile(schema_provider=provider)
    _second_record = second_bundle.compile(schema_provider=provider)
    raise RuntimeError(
        "warm session smoke stopped: approved-record runtime transport is not "
        "available; use the T14 runtime boundary before queueing"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check two workflow references through the approved-record boundary."
    )
    parser.add_argument("first", help="First workflow reference or path.")
    parser.add_argument("second", nargs="?", help="Second workflow reference or path; defaults to first.")
    parser.add_argument("--ready", action="store_true")
    parser.add_argument("--backend", default="api")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
