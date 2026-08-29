"""Headless VibeComfy agent CLI.

Usage::

    python -m vibecomfy.agent "explain this graph" --output-dir ./out
    python -m vibecomfy.agent --query "is there a faster way?" \
        --workflow ./workflow.json --dry-run --output-dir ./out

The CLI always sets ``VIBECOMFY_HEADLESS=1`` before importing the service so
that no ComfyUI/aiohttp route registration is triggered.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _load_graph(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"Workflow file not found: {path}")
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Workflow file must contain a JSON object: {path}")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibecomfy-agent",
        description="Run the VibeComfy agent executor from the command line.",
    )
    parser.add_argument(
        "query_positional",
        nargs="?",
        help="User query (may also be supplied with --query).",
    )
    parser.add_argument("--query", "-q", default=None, help="User query.")
    parser.add_argument(
        "--workflow",
        "-w",
        default=None,
        help="Path to a JSON workflow/graph file to attach to the request.",
    )
    parser.add_argument(
        "--output-dir",
        "--output",
        "-o",
        dest="output_dir",
        default=None,
        help="Directory where artifacts are written (required for harness use).",
    )
    parser.add_argument(
        "--profile",
        "-p",
        default=None,
        help="Executor profile name (default profile if omitted).",
    )
    parser.add_argument(
        "--pipeline-mode",
        "--mode",
        choices=("staged", "threaded", "full", "two_step"),
        default=None,
        help=(
            "Agent deliberation mode: staged (default) or threaded. "
            "Legacy full/two_step aliases are accepted and normalized."
        ),
    )
    parser.add_argument("--session-id", default=None, help="Session id for durable turns.")
    parser.add_argument("--idempotency-key", default=None, help="Idempotency key.")
    parser.add_argument(
        "--live",
        default=True,
        action="store_true",
        help="Mark the run as live/agentic (default).",
    )
    parser.add_argument(
        "--no-live",
        dest="live",
        action="store_false",
        help="Mark the run as non-live (recorded in metadata only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify only: run no research, implement, or reply phases.",
    )
    parser.add_argument(
        "--research",
        choices=("auto", "required", "disabled"),
        default="auto",
        help="Research policy metadata for harnesses: auto, required, or disabled.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Signal intent to apply a candidate graph if one is produced.",
    )
    parser.add_argument(
        "--network",
        default=True,
        action="store_true",
        help="Allow provider-backed agent execution (default).",
    )
    parser.add_argument(
        "--no-network",
        dest="network",
        action="store_false",
        help="Refuse before provider readiness or executor dispatch.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Per-turn timeout in seconds (best-effort).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON result envelope instead of plain text.",
    )
    return parser


def _derive_query(args: argparse.Namespace) -> str:
    query = args.query or args.query_positional or ""
    return query.strip()


def _status_to_exit_code(status: str) -> int:
    if status in {"success", "dry_run"}:
        return 0
    if status == "blocked_prerequisite":
        return 1
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    query = _derive_query(args)
    if not query:
        parser.error("A query is required (positional argument or --query).")

    try:
        graph = _load_graph(args.workflow)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    os.environ["VIBECOMFY_HEADLESS"] = "1"

    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.agent.service import run_headless

    request = HeadlessAgentRequest(
        query=query,
        graph=graph,
        session_id=args.session_id,
        profile=args.profile,
        idempotency_key=args.idempotency_key,
        output_dir=args.output_dir,
        live=args.live,
        dry_run=args.dry_run,
        apply=args.apply,
        network=args.network,
        timeout=args.timeout,
        pipeline_mode=args.pipeline_mode,
        extra={"research": args.research},
    )

    result = run_headless(request, entrypoint="headless_cli")

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(f"status: {result.status}")
        print(f"ok: {result.ok}")
        if result.error:
            print(f"error: {result.error}")
        if result.artifacts:
            print(f"artifacts: {result.artifacts.get('output_dir')}")
        response = result.response
        reply = response.get("reply") or response.get("message")
        if reply:
            print(f"reply: {reply}")

    return _status_to_exit_code(result.status)


if __name__ == "__main__":
    raise SystemExit(main())
