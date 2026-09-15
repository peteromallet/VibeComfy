from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from vibecomfy.commands import runpod_setup


def _runpod_lifecycle_root() -> Path:
    configured = getattr(sys, "_vibecomfy_runpod_lifecycle_root", None)
    if configured:
        return Path(configured)
    configured_env = os.getenv("VIBECOMFY_RUNPOD_LIFECYCLE_ROOT")
    if configured_env:
        return Path(configured_env)
    return Path(__file__).resolve().parents[3] / "runpod-lifecycle"


def _runpod_lifecycle_main(argv: list[str]) -> int:
    try:
        from runpod_lifecycle.cli import main as runpod_main
    except ImportError:
        root = _runpod_lifecycle_root()
        src = root / "src"
        if not src.exists():
            print(
                "runpod-lifecycle is not installed. Install VibeComfy with `pip install -e '.[runpod-local]'` "
                "or set VIBECOMFY_RUNPOD_LIFECYCLE_ROOT for a local checkout.",
                file=sys.stderr,
            )
            return 1
        sys.path.insert(0, str(src))
        try:
            from runpod_lifecycle.cli import main as runpod_main
        except Exception as exc:
            print(f"could not import runpod-lifecycle: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    root = _runpod_lifecycle_root()
    try:
        from runpod_lifecycle.config import load_runpod_env
    except ImportError:
        # The pinned lifecycle release predates the shared environment loader.
        # Keep it usable while newer installations own shared-file precedence.
        from dotenv import load_dotenv as load_runpod_env
    load_runpod_env(root / ".env")
    return runpod_main(argv)


def _cmd_runpod_list(args: argparse.Namespace) -> int:
    argv = ["list"]
    if args.name_prefix:
        argv.extend(["--name-prefix", args.name_prefix])
    if args.json:
        argv.append("--json")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_status(args: argparse.Namespace) -> int:
    return _runpod_lifecycle_main(["status", args.pod_id])


def _cmd_runpod_terminate(args: argparse.Namespace) -> int:
    argv = ["terminate", args.pod_id]
    if args.yes:
        argv.append("--yes")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_gpu_types(args: argparse.Namespace) -> int:
    argv = ["gpu-types"]
    if args.json:
        argv.append("--json")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_corpus_matrix(args: argparse.Namespace) -> int:
    script = Path("scripts/runpod_corpus_matrix.py")
    if not script.exists():
        print("scripts/runpod_corpus_matrix.py not found; run from the VibeComfy repo root", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(script)])


def _cmd_runpod_prepare_comfy(args: argparse.Namespace) -> int:
    try:
        runpod_setup.link_vibecomfy_custom_node(
            custom_nodes=args.custom_nodes,
            dry_run=args.dry_run,
        )
    except FileExistsError as exc:
        print(f"VibeComfy custom node link skipped: {exc}")
    if args.profile == "baseline":
        if args.install_python_deps:
            runpod_setup.install_python_deps(dry_run=args.dry_run)
        runpod_setup.stage_baseline_models(
            models_root=args.models_root,
            registry=args.registry,
            dry_run=args.dry_run,
        )
        parked = runpod_setup.park_node_packs(
            custom_nodes=args.custom_nodes,
            disabled_custom_nodes=args.disabled_custom_nodes,
            dry_run=args.dry_run,
        )
        for item in parked:
            if item.changed:
                action = "would park" if args.dry_run else "parked"
                print(f"{action} {item.name}: {item.source} -> {item.target}")
        return 0
    if args.profile == "ltx":
        if args.install_python_deps:
            runpod_setup.install_python_deps(dry_run=args.dry_run)
        runpod_setup.stage_ltx_models(
            models_root=args.models_root,
            registry=args.registry,
            full=args.full,
            dry_run=args.dry_run,
        )
        print("ltx profile staged LTX models. ResAdapter stays parked so SD1.5 and LTX can share one ComfyUI process.")
        return 0
    raise ValueError(f"unknown profile: {args.profile}")


def _cmd_runpod_install_nodes(args: argparse.Namespace) -> int:
    try:
        linked = runpod_setup.link_vibecomfy_custom_node(
            custom_nodes=args.custom_nodes,
            dry_run=args.dry_run,
        )
        if linked.changed:
            action = "would link" if args.dry_run else "linked"
            print(f"{action} VibeComfy custom node: {linked.target} -> {linked.source}")
    except FileExistsError as exc:
        print(f"VibeComfy custom node link skipped: {exc}")
    installed = runpod_setup.install_node_packs(
        custom_nodes=args.custom_nodes,
        lockfile=args.lockfile,
        node_packs=args.node_pack or runpod_setup.LTX_NODE_PACKS,
        install_requirements=not args.no_requirements,
        dry_run=args.dry_run,
    )
    for item in installed:
        action = "would install" if args.dry_run else ("installed" if item.changed else "verified")
        print(f"{action} {item.name} @ {item.commit}: {item.path}")
    return 0


def _cmd_runpod_install_torch(args: argparse.Namespace) -> int:
    runpod_setup.install_runpod_torch(
        python=args.python,
        dry_run=args.dry_run,
    )
    return 0


def _cmd_runpod_bootstrap_comfy(args: argparse.Namespace) -> int:
    runtime_root = args.runtime_root
    runpod_setup.ensure_runtime_layout(runtime_root=runtime_root, dry_run=args.dry_run)
    env = runpod_setup.runtime_environment(runtime_root=runtime_root)
    os.environ.update({key: os.environ.get(key, value) for key, value in env.items()})
    runpod_setup.write_extra_model_paths(runtime_root=runtime_root, dry_run=args.dry_run)
    runpod_setup.ensure_smoke_inputs(runtime_root=runtime_root, dry_run=args.dry_run)
    if not args.skip_torch_fix:
        runpod_setup.install_runpod_torch(
            python=str(Path(args.comfyui_executable).with_name("python")) if "/" in args.comfyui_executable else sys.executable,
            dry_run=args.dry_run,
        )
    installed = runpod_setup.install_node_packs(
        custom_nodes=runtime_root / "custom_nodes",
        lockfile=args.lockfile,
        node_packs=args.node_pack or runpod_setup.LTX_NODE_PACKS,
        install_requirements=not args.no_requirements,
        dry_run=args.dry_run,
    )
    for item in installed:
        action = "would install" if args.dry_run else ("installed" if item.changed else "verified")
        print(f"{action} {item.name} @ {item.commit}: {item.path}")
    try:
        linked = runpod_setup.link_vibecomfy_custom_node(
            custom_nodes=runtime_root / "custom_nodes",
            dry_run=args.dry_run,
        )
        if linked.changed:
            action = "would link" if args.dry_run else "linked"
            print(f"{action} VibeComfy custom node: {linked.target} -> {linked.source}")
    except FileExistsError as exc:
        print(f"VibeComfy custom node link skipped: {exc}")
    if not args.skip_models:
        runpod_setup.stage_baseline_models(
            models_root=runtime_root / "models",
            registry=args.registry,
            dry_run=args.dry_run,
        )
        runpod_setup.park_node_packs(
            custom_nodes=runtime_root / "custom_nodes",
            disabled_custom_nodes=runtime_root / "disabled_custom_nodes",
            dry_run=args.dry_run,
        )
        runpod_setup.stage_ltx_models(
            models_root=runtime_root / "models",
            registry=args.registry,
            full=args.full_ltx,
            dry_run=args.dry_run,
        )
    command = runpod_setup.comfy_serve_command(
        runtime_root=runtime_root,
        external_address=args.external_address,
        port=args.port,
        comfyui_executable=args.comfyui_executable,
    )
    print("\n# Runtime environment")
    for key, value in env.items():
        print(f"export {key}={shlex.quote(value)}")
    print("\n# Start ComfyUI")
    print(" ".join(shlex.quote(part) for part in command))
    return 0


def register(subparsers) -> None:
    runpod = subparsers.add_parser("runpod")
    runpod_sub = runpod.add_subparsers(dest="subcmd", required=True)

    runpod_list = runpod_sub.add_parser("list")
    runpod_list.add_argument("--name-prefix")
    runpod_list.add_argument("--json", action="store_true")
    runpod_list.set_defaults(func=_cmd_runpod_list)

    runpod_status = runpod_sub.add_parser("status")
    runpod_status.add_argument("pod_id")
    runpod_status.set_defaults(func=_cmd_runpod_status)

    runpod_terminate = runpod_sub.add_parser("terminate")
    runpod_terminate.add_argument("pod_id")
    runpod_terminate.add_argument("--yes", "-y", action="store_true")
    runpod_terminate.set_defaults(func=_cmd_runpod_terminate)

    runpod_gpu_types = runpod_sub.add_parser("gpu-types")
    runpod_gpu_types.add_argument("--json", action="store_true")
    runpod_gpu_types.set_defaults(func=_cmd_runpod_gpu_types)

    runpod_corpus = runpod_sub.add_parser("corpus-matrix")
    runpod_corpus.set_defaults(func=_cmd_runpod_corpus_matrix)

    prepare = runpod_sub.add_parser("prepare-comfy")
    prepare.add_argument("--profile", choices=("baseline", "ltx"), default="baseline")
    prepare.add_argument("--models-root", type=Path, default=Path("/workspace/vibecomfy/models"))
    prepare.add_argument("--custom-nodes", type=Path, default=Path("/workspace/vibecomfy/custom_nodes"))
    prepare.add_argument("--disabled-custom-nodes", type=Path, default=Path("/workspace/vibecomfy/disabled_custom_nodes"))
    prepare.add_argument("--registry", type=Path, default=None)
    prepare.add_argument("--install-python-deps", action="store_true")
    prepare.add_argument("--full", action="store_true", help="For --profile ltx, stage every phase:ltx registry asset.")
    prepare.add_argument("--dry-run", action="store_true")
    prepare.set_defaults(func=_cmd_runpod_prepare_comfy)

    install_nodes = runpod_sub.add_parser("install-nodes")
    install_nodes.add_argument("--custom-nodes", type=Path, default=Path("/workspace/vibecomfy/custom_nodes"))
    install_nodes.add_argument("--lockfile", type=Path, default=Path("custom_nodes.lock"))
    install_nodes.add_argument(
        "--node-pack",
        action="append",
        default=None,
        help="Node pack from custom_nodes.lock to install. Repeat to override/extend the default LTX set.",
    )
    install_nodes.add_argument("--no-requirements", action="store_true")
    install_nodes.add_argument("--dry-run", action="store_true")
    install_nodes.set_defaults(func=_cmd_runpod_install_nodes)

    install_torch = runpod_sub.add_parser("install-torch")
    install_torch.add_argument("--python", default=sys.executable)
    install_torch.add_argument("--dry-run", action="store_true")
    install_torch.set_defaults(func=_cmd_runpod_install_torch)

    bootstrap = runpod_sub.add_parser("bootstrap-comfy")
    bootstrap.add_argument("--runtime-root", type=Path, default=Path("/workspace/vibecomfy"))
    bootstrap.add_argument("--lockfile", type=Path, default=Path("custom_nodes.lock"))
    bootstrap.add_argument("--registry", type=Path, default=None)
    bootstrap.add_argument("--port", type=int, default=19123)
    bootstrap.add_argument("--external-address")
    bootstrap.add_argument("--comfyui-executable", default="comfyui")
    bootstrap.add_argument(
        "--node-pack",
        action="append",
        default=None,
        help="Node pack from custom_nodes.lock to install. Repeat to override/extend the default LTX set.",
    )
    bootstrap.add_argument("--no-requirements", action="store_true")
    bootstrap.add_argument("--skip-models", action="store_true")
    bootstrap.add_argument("--skip-torch-fix", action="store_true")
    bootstrap.add_argument("--full-ltx", action="store_true", help="Stage every phase:ltx registry asset instead of the basic TTV set.")
    bootstrap.add_argument("--dry-run", action="store_true")
    bootstrap.set_defaults(func=_cmd_runpod_bootstrap_comfy)
