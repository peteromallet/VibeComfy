from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from vibecomfy.errors import RuntimeNodeError
from vibecomfy.registry.library import load_workflow_reference
from vibecomfy.runtime.client import ComfyClient
from vibecomfy.runtime.eval import compile_eval_subgraph
from vibecomfy.runtime.run import smoke_runtime_sync
from vibecomfy.runtime.session import EmbeddedSession, SessionConfig
from vibecomfy.schema import get_schema_provider


def _cmd_runtime_doctor(args: argparse.Namespace) -> int:
    payload = build_runtime_doctor_payload()
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for line in payload["messages"]:
            print(line)
    return 0


def build_runtime_doctor_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "runtime_modes": ["embedded", "managed", "external"],
        "default_run_mode": "auto",
        "messages": [
            "runtime modes: embedded, managed, external",
            "default `vibecomfy run` mode: auto",
            "use `vibecomfy session start` to create a reusable managed HTTP server",
            "use `vibecomfy run --runtime server` for one-shot managed HTTP server mode",
            "use `vibecomfy run --runtime server --server-url URL` for external HTTP server mode",
        ],
    }


def _cmd_runtime_smoke(args: argparse.Namespace) -> int:
    if args.mode not in {"managed", "external"}:
        print(f"unknown smoke mode: {args.mode}", file=sys.stderr)
        return 2
    server_url = args.server_url if args.mode == "external" else None
    result = smoke_runtime_sync(server_url=server_url)
    print(json.dumps(result, indent=2))
    return 0


def _cmd_runtime_eval_node(args: argparse.Namespace) -> int:
    try:
        schema_provider = get_schema_provider("auto", server_url=args.server_url)
        workflow = load_workflow_reference(
            args.path,
            schema_provider=schema_provider,
            allow_scratchpad=True,
            ready=getattr(args, "ready", False),
        )

        target_node = args.node
        subgraph = compile_eval_subgraph(workflow, target_node)

        # Build base result metadata
        node_info = workflow.lookup_id(target_node)
        result: dict = {
            "node_id": target_node,
            "class_type": node_info.get("class_type"),
            "previewable": True,
            "outputs": {},
        }

        if isinstance(subgraph, dict) and subgraph.get("previewable") is False:
            result["previewable"] = False
            result["outputs"] = subgraph
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(
                    f"Node {target_node} ({subgraph.get('class_type')}) "
                    f"is not visualizable (output type: {subgraph.get('type')})"
                )
            return 0

        # Queue through the selected runtime
        runtime = getattr(args, "runtime", "embedded")
        if runtime == "runpod":
            if not _has_runpod_credentials():
                print(
                    "RunPod eval-node not available without credentials. "
                    "Use --runtime embedded or --runtime server.",
                    file=sys.stderr,
                )
                return 2
            raise RuntimeNodeError(
                "RunPod eval-node is not yet implemented",
                next_action="vibecomfy runtime doctor",
            )

        elif runtime == "embedded":
            queue_result = asyncio.run(_queue_embedded(subgraph))

        elif runtime == "server":
            server_url = args.server_url
            if not server_url:
                print(
                    "--server-url is required for --runtime server",
                    file=sys.stderr,
                )
                return 2
            queue_result = asyncio.run(_queue_server(subgraph, server_url))

        else:
            print(f"unknown runtime: {runtime}", file=sys.stderr)
            return 2

        result["outputs"] = queue_result
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            node_id = result["node_id"]
            class_type = result["class_type"]
            print(f"node_id: {node_id}")
            print(f"class_type: {class_type}")
            print(f"previewable: {result['previewable']}")
            outputs = result.get("outputs", {})
            if isinstance(outputs, dict):
                prompt_id = outputs.get("prompt_id")
                if prompt_id:
                    print(f"prompt_id: {prompt_id}")
        return 0

    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"eval-node failed: {exc}", file=sys.stderr)
        return 1


async def _queue_embedded(api_dict: dict) -> dict:
    """Queue an eval subgraph through an embedded ComfyUI session."""
    session = EmbeddedSession(SessionConfig())
    try:
        await session.start()
        assert session._comfy is not None
        queued = await session._comfy.queue_prompt_api(api_dict)
    finally:
        await session.stop()
    return queued if isinstance(queued, dict) else {"prompt_id": str(queued)}


async def _queue_server(api_dict: dict, server_url: str) -> dict:
    """Queue an eval subgraph through a server ComfyUI instance."""
    client = ComfyClient(server_url)
    return await client.queue_prompt(api_dict)


def _has_runpod_credentials() -> bool:
    """Check whether RunPod credentials are configured."""
    if os.environ.get("RUNPOD_API_KEY"):
        return True
    runpod_config = os.environ.get("RUNPOD_CONFIG_PATH")
    if runpod_config and os.path.exists(runpod_config):
        return True
    return False


def register(subparsers) -> None:
    runtime = subparsers.add_parser("runtime")
    runtime_sub = runtime.add_subparsers(dest="subcmd", required=True)
    runtime_doctor = runtime_sub.add_parser("doctor")
    runtime_doctor.add_argument("--json", action="store_true")
    runtime_doctor.set_defaults(func=_cmd_runtime_doctor)
    runtime_smoke = runtime_sub.add_parser("smoke")
    runtime_smoke.add_argument("--mode", default="managed")
    runtime_smoke.add_argument("--server-url")
    runtime_smoke.set_defaults(func=_cmd_runtime_smoke)
    eval_node = runtime_sub.add_parser("eval-node")
    eval_node.add_argument("path")
    eval_node.add_argument("--node", required=True)
    eval_node.add_argument(
        "--runtime", choices=["embedded", "server", "runpod"], default="embedded"
    )
    eval_node.add_argument("--server-url")
    eval_node.add_argument("--ready", action="store_true")
    eval_node.add_argument("--json", action="store_true")
    eval_node.set_defaults(func=_cmd_runtime_eval_node)
