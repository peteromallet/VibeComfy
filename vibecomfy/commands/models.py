from __future__ import annotations

import argparse
from pathlib import Path

import vibecomfy.fetch as fetch_assets
from vibecomfy.commands._model_ensure import (
    command_args as _cmd_models_ensure,
    command_register_args as _cmd_models_register,
)
from vibecomfy.registry import models_loader


def _cmd_models_stage(args: argparse.Namespace) -> int:
    entries = models_loader.load_registry(args.registry)
    selected = models_loader._filter_entries(entries, ids=args.ids, select_phase=args.select_phase)
    models_root = args.models_root if args.models_root is not None else fetch_assets.models_root()
    if args.dry_run:
        models_loader._print_dry_run(selected, models_root=models_root)
    else:
        models_loader.stage_many(selected, models_root=models_root)
    return 0


def register(subparsers) -> None:
    models = subparsers.add_parser("models")
    models_sub = models.add_subparsers(dest="subcmd", required=True)
    stage = models_sub.add_parser("stage")
    stage.add_argument("--registry", type=Path, default=models_loader.DEFAULT_REGISTRY_PATH)
    stage.add_argument("--models-root", type=Path)
    selector = stage.add_mutually_exclusive_group()
    selector.add_argument("--ids", nargs="+")
    selector.add_argument("--select-phase", choices=("core", "gguf", "ltx", "wan_wrapper", "qwen_image"))
    stage.add_argument("--dry-run", action="store_true")
    stage.set_defaults(func=_cmd_models_stage)

    ensure = models_sub.add_parser(
        "ensure",
        help="reconcile authored and registry-resolved assets for one workflow",
    )
    ensure.add_argument("workflow")
    ensure.add_argument("--models-root", type=Path)
    ensure.add_argument("--dry-run", action="store_true")
    ensure.add_argument("--force", action="store_true")
    ensure.add_argument(
        "--force-verify",
        action="store_true",
        help="stream-hash present files even when a matching verification receipt exists",
    )
    ensure.set_defaults(func=_cmd_models_ensure)

    register_model = models_sub.add_parser(
        "register",
        help="record an agent-researched URL mapping in a workflow-local sidecar",
    )
    register_model.add_argument("workflow")
    register_model.add_argument("model_ref", help="unresolved model filename/value")
    register_model.add_argument("--url", required=True)
    register_model.add_argument("--target-path", required=True, help="destination relative to models root")
    register_model.add_argument("--sha256")
    register_model.add_argument("--size-bytes", type=int)
    register_model.set_defaults(func=_cmd_models_register)


__all__ = ["register"]
