"""CLI commands: config show | config set-library | config init."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vibecomfy.local_library import (
    Slot,
    SlotState,
    detect_comfy_install,
    resolve,
    validate_custom_nodes_dir,
    validate_models_dir,
    write_slot,
)


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "config",
        help="Show or update VibeComfy local-library configuration.",
    )
    sub = p.add_subparsers(dest="config_cmd", required=True)
    _register_show(sub)
    _register_set_library(sub)
    _register_init(sub)


# ── Sub-command registration ──────────────────────────────────────────────────


def _register_show(sub) -> None:
    p = sub.add_parser("show", help="Print resolved local-library slot states.")
    p.add_argument("--json", dest="json_out", action="store_true",
                   help="Emit JSON instead of human-readable text.")
    p.set_defaults(func=_cmd_show)


def _register_set_library(sub) -> None:
    p = sub.add_parser(
        "set-library",
        help="Persist custom_nodes and/or models paths in the VibeComfy config.",
    )
    cn_group = p.add_mutually_exclusive_group()
    cn_group.add_argument(
        "--custom-nodes", metavar="PATH",
        help="Absolute path to the ComfyUI custom_nodes directory.",
    )
    cn_group.add_argument(
        "--no-custom-nodes", action="store_true",
        help="Disable the custom_nodes slot (write sentinel 'disabled').",
    )
    mo_group = p.add_mutually_exclusive_group()
    mo_group.add_argument(
        "--models", metavar="PATH",
        help="Absolute path to the ComfyUI models root directory.",
    )
    mo_group.add_argument(
        "--no-models", action="store_true",
        help="Disable the models slot (write sentinel 'disabled').",
    )
    p.add_argument("--repo", action="store_true",
                   help="Write to repo-level vibecomfy.toml (CWD) instead of ~/.vibecomfy.")
    p.add_argument("--force", action="store_true",
                   help="Allow directories that look empty/unusual (looks_real signal).")
    p.set_defaults(func=_cmd_set_library)


def _register_init(sub) -> None:
    p = sub.add_parser(
        "init",
        help="Auto-detect ComfyUI and write detected paths to config.",
    )
    p.add_argument("--repo", action="store_true",
                   help="Write to repo-level vibecomfy.toml.")
    p.add_argument("--yes", "-y", dest="assume_yes", action="store_true",
                   help="Skip confirmation prompt.")
    p.set_defaults(func=_cmd_init)


# ── Command implementations ───────────────────────────────────────────────────


def _cmd_show(args: argparse.Namespace) -> int:
    cn = resolve(Slot.custom_nodes)
    mo = resolve(Slot.models)

    if getattr(args, "json_out", False):
        print(json.dumps({
            "custom_nodes": {
                "state": cn.state.name,
                "path": str(cn.path) if cn.path is not None else None,
                "source": cn.source,
            },
            "models": {
                "state": mo.state.name,
                "path": str(mo.path) if mo.path is not None else None,
                "source": mo.source,
            },
        }, indent=2))
        return 0

    def _fmt(r: object, label: str) -> None:
        from vibecomfy.local_library import SlotResolution
        assert isinstance(r, SlotResolution)
        if r.state is SlotState.SET:
            print(f"  {label}: {r.path}  [source: {r.source}]")
        elif r.state is SlotState.DISABLED:
            print(f"  {label}: disabled  [source: {r.source}]")
        else:
            print(f"  {label}: unset  [source: {r.source}]")

    print("Local-library config:")
    _fmt(cn, "custom_nodes")
    _fmt(mo, "models")
    return 0


def _cmd_set_library(args: argparse.Namespace) -> int:
    repo_root: Path | None = Path.cwd() if getattr(args, "repo", False) else None
    changes: list[tuple[Slot, str]] = []

    cn_path: str | None = getattr(args, "custom_nodes", None)
    no_cn: bool = getattr(args, "no_custom_nodes", False)
    if cn_path is not None:
        rc = _validate_path_arg(cn_path, Slot.custom_nodes, args)
        if rc != 0:
            return rc
        changes.append((Slot.custom_nodes, cn_path))
    elif no_cn:
        changes.append((Slot.custom_nodes, "disabled"))

    mo_path: str | None = getattr(args, "models", None)
    no_mo: bool = getattr(args, "no_models", False)
    if mo_path is not None:
        rc = _validate_path_arg(mo_path, Slot.models, args)
        if rc != 0:
            return rc
        changes.append((Slot.models, mo_path))
    elif no_mo:
        changes.append((Slot.models, "disabled"))

    if not changes:
        print(
            "No changes requested — supply --custom-nodes, --no-custom-nodes, "
            "--models, or --no-models.",
            file=sys.stderr,
        )
        return 1

    for slot, value in changes:
        out_path = write_slot(slot, value, repo=repo_root)
        print(f"Wrote {slot.value} = {value!r} to {out_path}")

    return 0


def _validate_path_arg(raw: str, slot: Slot, args: argparse.Namespace) -> int:
    """Return 0 if acceptable, non-zero otherwise (printing error to stderr)."""
    p = Path(raw)
    signal = validate_custom_nodes_dir(p) if slot is Slot.custom_nodes else validate_models_dir(p)

    if signal == "missing":
        print(f"error: {slot.value} path does not exist: {raw}", file=sys.stderr)
        return 2
    if signal == "not_a_directory":
        print(f"error: {slot.value} path is not a directory: {raw}", file=sys.stderr)
        return 2
    if signal == "looks_real" and not getattr(args, "force", False):
        print(
            f"warning: {slot.value} path looks empty or unexpected: {raw}\n"
            f"  Pass --force to set it anyway.",
            file=sys.stderr,
        )
        return 3
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    comfy_root, models_dir = detect_comfy_install()

    if comfy_root is None:
        print("No ComfyUI installation detected.", file=sys.stderr)
        print("Set COMFYUI_PATH or install ComfyUI, then re-run `config init`.", file=sys.stderr)
        return 1

    custom_nodes_dir: Path | None = comfy_root / "custom_nodes"
    if not custom_nodes_dir.is_dir():
        custom_nodes_dir = None

    print(f"Detected ComfyUI at: {comfy_root}")
    if custom_nodes_dir:
        print(f"  custom_nodes: {custom_nodes_dir}")
    if models_dir:
        print(f"  models:       {models_dir}")

    if not getattr(args, "assume_yes", False):
        try:
            answer = input("Apply these settings? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            return 1
        if answer not in {"y", "yes"}:
            print("Aborted.", file=sys.stderr)
            return 1

    repo_root: Path | None = Path.cwd() if getattr(args, "repo", False) else None

    if custom_nodes_dir is not None:
        out = write_slot(Slot.custom_nodes, str(custom_nodes_dir), repo=repo_root)
        print(f"Wrote custom_nodes to {out}")

    if models_dir is not None:
        out = write_slot(Slot.models, str(models_dir), repo=repo_root)
        print(f"Wrote models to {out}")

    return 0
