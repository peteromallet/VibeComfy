from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from vibecomfy.runtime.client import ComfyClient
from vibecomfy.runtime.model_policy import normalized_models_root
from vibecomfy.runtime.session import (
    ServerSession,
    SessionConfig,
    _cleanup_session_files,
    _comfy_server_argv,
    _session_ready,
    current_source_revision,
    find_active_session,
)


def _session_dir(id_: str) -> Path:
    return Path("out/sessions") / id_


def _config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    memory_profile = getattr(args, "memory_profile", None)
    config: dict[str, Any] = {
        "port": args.port,
    }
    if memory_profile is not None:
        config["memory_profile"] = memory_profile
        if args.vram_policy is not None:
            config["vram_policy"] = args.vram_policy
        if args.cache_policy is not None:
            config["cache_policy"] = args.cache_policy
        if args.disable_smart_memory:
            config["disable_smart_memory"] = args.disable_smart_memory
    else:
        config["vram_policy"] = args.vram_policy or "auto"
        config["cache_policy"] = args.cache_policy or "smart"
        config["disable_smart_memory"] = args.disable_smart_memory
    config["warm_policy"] = args.warm_policy or "auto"
    if args.reserve_vram_gb is not None:
        config["reserve_vram_gb"] = args.reserve_vram_gb
    input_directory = getattr(args, "input_directory", None)
    output_directory = getattr(args, "output_directory", None)
    temp_directory = getattr(args, "temp_directory", None)
    if input_directory is not None:
        config["input_directory"] = input_directory
    if output_directory is not None:
        config["output_directory"] = output_directory
    if temp_directory is not None:
        config["temp_directory"] = temp_directory
    ready_timeout_sec = getattr(args, "ready_timeout_sec", None)
    if ready_timeout_sec is not None:
        config["ready_timeout_sec"] = ready_timeout_sec
    config["models_root"] = normalized_models_root()
    config["models_root_normalized"] = normalized_models_root()
    config["locality"] = "managed_local_server"
    return config


async def _daemon_main(args: argparse.Namespace) -> int:
    config_dict = json.loads(args.config)
    if not isinstance(config_dict, dict):
        raise ValueError("--config must decode to a JSON object")
    session = ServerSession(SessionConfig.from_dict(config_dict))
    session_dir = _session_dir(args.id)
    stop_event = asyncio.Event()
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "server_argv.json").write_text(
        json.dumps(list(_comfy_server_argv(session.config)), indent=2),
        encoding="utf-8",
    )

    def request_stop() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: request_stop())

    try:
        await session.start()
        (session_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
        (session_dir / "url").write_text(str(session.url), encoding="utf-8")
        (session_dir / "config.json").write_text(
            json.dumps(config_dict, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        revision = current_source_revision()
        if revision is not None:
            (session_dir / "source_revision").write_text(revision, encoding="utf-8")
        await stop_event.wait()
    finally:
        await session.stop()
        _cleanup_session_files(session_dir)
    return 0


def _cmd_session_start(args: argparse.Namespace) -> int:
    session_dir = _session_dir(args.id)
    # Clear stale markers before spawning (shared readiness contract)
    _cleanup_session_files(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    config = _config_from_args(args)
    config.setdefault("server_log_path", str(session_dir / "comfy.log"))
    log_path = session_dir / "daemon.log"
    cmd = [
        sys.executable,
        "-m",
        "vibecomfy.commands.session",
        "--daemon",
        "--id",
        args.id,
        "--config",
        json.dumps(config),
    ]
    (session_dir / "daemon_argv.json").write_text(json.dumps(cmd, indent=2), encoding="utf-8")
    with log_path.open("ab", buffering=0) as stderr:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
            start_new_session=True,
        )
    ready_timeout_sec = int(config.get("ready_timeout_sec") or os.environ.get("VIBECOMFY_SESSION_READY_TIMEOUT_SEC") or 300)
    for _ in range(ready_timeout_sec):
        if _session_ready(session_dir):
            url = (session_dir / "url").read_text(encoding="utf-8").strip()
            print(f"session {args.id}: {url}")
            return 0
        if process.poll() is not None:
            print(f"session {args.id} failed to start; see {log_path}", file=sys.stderr)
            return 1
        time.sleep(1)
    print(f"session {args.id} did not become ready within {ready_timeout_sec} seconds", file=sys.stderr)
    sys.stderr.flush()
    _terminate_daemon_process(process)
    return 1


def _terminate_daemon_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def _cmd_session_stop(args: argparse.Namespace) -> int:
    session_dir = _session_dir(args.id)
    pid_path = session_dir / "pid"
    if not pid_path.exists():
        _cleanup_session_files(session_dir)
        print(f"session {args.id}: not running")
        return 0
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _cleanup_session_files(session_dir)
        print(f"session {args.id}: stopped")
        return 0
    except (OSError, ValueError) as exc:
        print(f"session {args.id}: stop failed: {exc}", file=sys.stderr)
        return 1

    for _ in range(100):
        if not pid_path.exists():
            print(f"session {args.id}: stopped")
            return 0
        time.sleep(0.1)
    _cleanup_session_files(session_dir)
    print(f"session {args.id}: stop requested")
    return 0


def _cmd_session_list(args: argparse.Namespace) -> int:
    root = Path("out/sessions")
    if not root.exists():
        return 0
    for session_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        url = find_active_session(session_dir.name)
        if url:
            print(f"{session_dir.name}\t{url}")
    return 0


def _cmd_session_status(args: argparse.Namespace) -> int:
    url = find_active_session(args.id)
    if not url:
        print(f"session {args.id}: not running")
        return 1
    print(f"session {args.id}: {url}")
    return 0


def _cmd_session_flush(args: argparse.Namespace) -> int:
    url = find_active_session(args.id)
    if not url:
        print(f"session {args.id}: not running", file=sys.stderr)
        return 1
    asyncio.run(
        ComfyClient(url).free(unload_models=args.unload_models, free_memory=args.free_memory)
    )
    print(f"session {args.id}: flush queued")
    return 0


def register(subparsers) -> None:
    session = subparsers.add_parser("session")
    session_sub = session.add_subparsers(dest="subcmd", required=True)

    start = session_sub.add_parser("start")
    start.add_argument("--id", default="default")
    start.add_argument("--vram-policy", choices=["auto", "high", "low", "normal"])
    start.add_argument("--reserve-vram-gb", type=float)
    start.add_argument("--cache-policy")
    start.add_argument("--disable-smart-memory", action="store_true")
    start.add_argument("--warm-policy", choices=["auto", "always", "never"])
    start.add_argument("--memory-profile", type=int, choices=[1, 2, 3, 4, 5])
    start.add_argument("--port", type=int, default=8188)
    start.add_argument("--input-directory")
    start.add_argument("--output-directory")
    start.add_argument("--temp-directory")
    start.add_argument("--ready-timeout-sec", type=int)
    start.set_defaults(func=_cmd_session_start)

    stop = session_sub.add_parser("stop")
    stop.add_argument("id")
    stop.set_defaults(func=_cmd_session_stop)

    list_ = session_sub.add_parser("list")
    list_.set_defaults(func=_cmd_session_list)

    flush = session_sub.add_parser("flush")
    flush.add_argument("id")
    flush.add_argument("--unload-models", action=argparse.BooleanOptionalAction, default=True)
    flush.add_argument("--free-memory", action=argparse.BooleanOptionalAction, default=True)
    flush.set_defaults(func=_cmd_session_flush)

    status = session_sub.add_parser("status")
    status.add_argument("id")
    status.set_defaults(func=_cmd_session_status)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vibecomfy.commands.session")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--id", default="default")
    parser.add_argument("--config", default="{}")
    args = parser.parse_args(argv)
    if not args.daemon:
        parser.error("--daemon is required for module execution")
    return asyncio.run(_daemon_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
