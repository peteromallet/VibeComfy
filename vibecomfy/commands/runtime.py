from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vibecomfy.cli_loader import load_bundle
from vibecomfy.local_library import Slot, resolve
from vibecomfy.runtime.eval import eval_node_sync
from vibecomfy.runtime.run import smoke_runtime_sync


def _cmd_runtime_doctor(args: argparse.Namespace) -> int:
    payload = build_runtime_doctor_payload()
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for line in payload["messages"]:
            print(line)
    return 0


def _pip_comfy_package_importable() -> bool:
    """True when a pip-installed ``comfy`` package exists in site-packages.

    A bare ``import comfy`` is not reliable here: when the command runs from
    inside a ComfyUI checkout, the checkout's ``comfy/`` dir shadows the pip
    install on ``sys.path``.  Probe site-packages directly instead.
    """
    import site  # noqa: PLC0415

    site_dirs = [Path(site.getsitepackages()[0])] if site.getsitepackages() else []
    user_dir = site.getusersitepackages()
    if user_dir:
        site_dirs.append(Path(user_dir))
    for site_dir in site_dirs:
        if (site_dir / "comfy" / "__init__.py").is_file():
            return True
    return False


def _checkout_comfy_dir_present() -> bool:
    """True when a checkout of the ComfyUI ``comfy/`` package dir is on disk.

    Detects either a nested checkout at ``cwd/comfy/comfy`` or a ComfyUI root
    whose ``main.py`` sits next to its ``comfy/`` package directory.
    """
    cwd = Path.cwd()
    if (cwd / "comfy" / "comfy" / "__init__.py").is_file():
        return True
    if (cwd / "main.py").is_file() and (cwd / "comfy" / "__init__.py").is_file():
        return True
    return False


def build_runtime_doctor_payload() -> dict[str, object]:
    comfy_root, comfy_models = _detected_comfy_install()
    custom_nodes = resolve(Slot.custom_nodes)
    models = resolve(Slot.models)
    embedded_ready = comfy_root is not None and _is_comfy_root(comfy_root)
    local_library = {
        "custom_nodes": _slot_payload(custom_nodes),
        "models": _slot_payload(models),
    }
    if embedded_ready:
        embedded = {
            "status": "ready",
            "comfy_root": str(comfy_root),
            "models_root": str(comfy_models) if comfy_models else None,
            "reason": "ComfyUI checkout contains server.py and nodes.py",
        }
    else:
        embedded = {
            "status": "not_ready",
            "comfy_root": str(comfy_root) if comfy_root else None,
            "models_root": str(comfy_models) if comfy_models else None,
            "reason": "No local ComfyUI root with server.py and nodes.py was detected",
            "next_action": "Set COMFYUI_PATH to a ComfyUI checkout or use --runtime server --server-url URL",
        }
    messages = [
        "runtime modes: embedded, managed, external",
        "default `vibecomfy run` mode: auto",
        "use `vibecomfy session start` to create a reusable managed HTTP server",
        "use `vibecomfy run --runtime server` for one-shot managed HTTP server mode",
        "use `vibecomfy run --runtime server --server-url URL` for external HTTP server mode",
    ]
    messages.extend(_readiness_messages(embedded, local_library))
    if _pip_comfy_package_importable() and _checkout_comfy_dir_present():
        messages.append(
            "WARNING: split-brain ComfyUI install detected: a pip `comfy` "
            "package and a checkout `comfy/` package dir are both present. "
            "The pip comfyui==0.26.0 pins frontend<1.46 while the checkout's "
            "requirements pin 1.48.x; the checkout comfy/ wins when running "
            "main.py. Keep their virtual environments separate."
        )
    return {
        "status": "ok",
        "readiness_status": "ready" if embedded_ready else "not_ready",
        "runtime_modes": ["embedded", "managed", "external"],
        "default_run_mode": "auto",
        "local_library": local_library,
        "readiness": {
            "embedded": embedded,
            "managed": {
                "status": "ready" if embedded_ready else "not_ready",
                "reason": "Managed mode uses the same local ComfyUI root as embedded mode",
            },
            "external": {
                "status": "unverified",
                "reason": "No external server URL was supplied; doctor does not claim a remote server is reachable",
                "next_action": "Run with --server-url URL or use `vibecomfy run --runtime server --server-url URL`",
            },
        },
        "messages": messages,
    }


def _detected_comfy_install() -> tuple[Path | None, Path | None]:
    """Detect a local checkout without importing ComfyUI modules."""
    from vibecomfy.local_library import detect_comfy_install

    root, models = detect_comfy_install()
    if root is not None and not _is_comfy_root(root):
        return None, None
    return root, models


def _is_comfy_root(root: Path) -> bool:
    return (root / "server.py").is_file() and (root / "nodes.py").is_file()


def _slot_payload(slot) -> dict[str, object]:
    return {
        "state": slot.state.name.lower(),
        "path": str(slot.path) if slot.path is not None else None,
        "exists": bool(slot.path and slot.path.is_dir()),
        "source": slot.source,
    }


def _readiness_messages(embedded: dict[str, object], library: dict[str, object]) -> list[str]:
    messages: list[str] = []
    if embedded["status"] == "ready":
        messages.append(f"embedded readiness: ready (ComfyUI root: {embedded['comfy_root']})")
    else:
        messages.append("embedded readiness: NOT READY (no local ComfyUI root with server.py and nodes.py)")
        messages.append("configure COMFYUI_PATH or provide an external server URL; configured model/node libraries do not make embedded runtime ready")
    for name, value in library.items():
        state = value["state"]
        exists = value["exists"]
        messages.append(f"{name} library: {state}, {'present' if exists else 'missing'}")
    messages.append("external readiness: UNVERIFIED (supply a server URL to test/use an external ComfyUI server)")
    return messages


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
        bundle = load_bundle(args.path)
        bundle.require_canonical_authority("runtime evaluation")
        result = eval_node_sync(
            bundle,
            args.node,
            runtime=getattr(args, "runtime", "embedded"),
            server_url=getattr(args, "server_url", None),
        )
        if getattr(args, "json", False):
            print(json.dumps(result.to_json(), indent=2, sort_keys=True))
        else:
            print(json.dumps(result.to_json(), indent=2, sort_keys=True))
        return 0

    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"eval-node failed: {exc}", file=sys.stderr)
        return 1


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
