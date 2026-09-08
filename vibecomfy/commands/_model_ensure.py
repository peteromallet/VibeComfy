"""Canonical workflow-scoped model reconciliation used by the CLI aliases."""

from __future__ import annotations

import argparse
import re
import shlex
import sys
from pathlib import Path

import vibecomfy.fetch as fetch_assets
import yaml
from vibecomfy.errors import ModelAssetError
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import get_schema_provider


def load_final_workflow(workflow_ref: str):
    """Load the same final ``VibeWorkflow`` that runtime preflight receives."""

    schema_provider = get_schema_provider("auto")
    return load_workflow_reference(
        workflow_ref,
        schema_provider=schema_provider,
        allow_scratchpad=True,
    )


def entries_for_workflow(workflow_ref: str) -> list[dict]:
    """Resolve authored and registry-backed picker assets from the final graph."""

    workflow = load_final_workflow(workflow_ref)
    # Import lazily so tests and runtime keep one authoritative resolver, rather
    # than growing a second CLI-only interpretation of model picker fields.
    from vibecomfy.runtime.session import _model_assets_from_workflow

    return _model_assets_from_workflow(workflow)


def reconcile_workflow_models(
    workflow_ref: str,
    *,
    models_root: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    force_verify: bool = False,
) -> int:
    """Reconcile all downloadable assets referenced by a final workflow."""

    try:
        entries = entries_for_workflow(workflow_ref)
        root = models_root if models_root is not None else fetch_assets.models_root()
        if dry_run:
            for entry in entries:
                path = fetch_assets.local_path(entry, root=root)
                status = "present" if fetch_assets.is_present(entry, root=root) else "would fetch"
                print(f"{status} {entry['name']} -> {path}")
            return 0
        download_kwargs = {"force": force, "root": root}
        if force_verify:
            download_kwargs["force_verify"] = True
        fetch_assets.download_many(entries, **download_kwargs)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        if isinstance(exc, ModelAssetError) and exc.message.startswith("unresolved workflow model assets:"):
            print(model_reconciliation_hint(workflow_ref, exc), file=sys.stderr)
        else:
            print(exc, file=sys.stderr)
        return 1
    return 0


def command_args(args: argparse.Namespace) -> int:
    return reconcile_workflow_models(
        args.workflow,
        models_root=getattr(args, "models_root", None),
        dry_run=bool(getattr(args, "dry_run", False)),
        force=bool(getattr(args, "force", False)),
        force_verify=bool(getattr(args, "force_verify", False)),
    )


def model_reconciliation_hint(
    workflow_ref: str,
    exc: ModelAssetError,
    *,
    shared_root: str | None = None,
) -> str:
    """Explain the agent research handoff and both deterministic CLI steps."""

    value_match = re.search(r"=(['\"])(.*?)\1", exc.message)
    value = value_match.group(2) if value_match else "MODEL_FILENAME"
    field_match = re.search(r"\.([A-Za-z0-9_]+)=", exc.message)
    subdir = {
        "ckpt_name": "checkpoints",
        "clip_name": "text_encoders",
        "clip_name1": "text_encoders",
        "clip_name2": "text_encoders",
        "lora_name": "loras",
        "model_name": "diffusion_models",
        "text_encoder": "text_encoders",
        "unet_name": "diffusion_models",
        "vae_name": "vae",
    }.get(field_match.group(1) if field_match else "", "diffusion_models")
    filename = value.replace("\\", "/").rsplit("/", 1)[-1]
    target = f"{subdir}/{filename}"
    register = (
        f"vibecomfy models register {shlex.quote(str(workflow_ref))} {shlex.quote(value)} "
        f"--url URL_FROM_RESEARCH --target-path {shlex.quote(target)}"
    )
    ensure = f"vibecomfy models ensure {shlex.quote(str(workflow_ref))}"
    if shared_root:
        ensure += f" --models-root {shlex.quote(str(shared_root))}"
    return (
        f"{exc.message}\nresearch need: find the authoritative URL and optional size/SHA pins for {value!r}; "
        f"then run `{register}` followed by `{ensure}`"
    )


def sidecar_path_for_workflow(workflow_ref: str) -> Path:
    workflow = load_final_workflow(workflow_ref)
    source_path = getattr(getattr(workflow, "source", None), "path", None)
    if not source_path:
        raise ValueError(
            "models register requires a file-backed workflow so its local sidecar can be stored"
        )
    return Path(source_path).with_suffix(".models.yaml")


def register_workflow_model(
    workflow_ref: str,
    model_ref: str,
    *,
    url: str,
    target_path: str,
    sha256: str | None = None,
    size_bytes: int | None = None,
) -> int:
    """Record one agent-researched mapping in the workflow-local sidecar."""

    sidecar = sidecar_path_for_workflow(workflow_ref)
    target = target_path.replace("\\", "/")
    if (
        "/" not in target
        or not target
        or target.startswith("/")
        or target.startswith("../")
        or "/../" in target
        or re.match(r"^[A-Za-z]:/", target)
    ):
        raise ValueError("--target-path must include a model directory and must not contain '..'")
    if size_bytes is not None and size_bytes < 0:
        raise ValueError("--size-bytes must be non-negative")
    entry_id = "local_" + re.sub(r"[^a-z0-9]+", "_", f"{model_ref}_{target}", flags=re.IGNORECASE).strip("_").lower()
    if not entry_id:
        raise ValueError("model reference and target path must produce a non-empty id")
    data: dict = {"models": []}
    if sidecar.exists():
        loaded = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict) or not isinstance(loaded.get("models", []), list):
            raise ValueError(f"invalid model sidecar: {sidecar}")
        data = loaded
    rows = [row for row in data["models"] if not isinstance(row, dict) or row.get("id") != entry_id]
    row = {
        "id": entry_id,
        "source": {"kind": "url", "url": url},
        "min_size": size_bytes or 0,
        "targets": [{"node_pack": "comfy_core", "path": target}],
    }
    if sha256:
        row["sha256"] = sha256
    if size_bytes is not None:
        row["size_bytes"] = size_bytes
    rows.append(row)
    data["models"] = rows
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    from vibecomfy.registry.models_loader import _clear_cache

    _clear_cache()
    print(f"registered {model_ref} -> {sidecar}")
    return 0


def command_register_args(args: argparse.Namespace) -> int:
    try:
        return register_workflow_model(
            args.workflow,
            args.model_ref,
            url=args.url,
            target_path=args.target_path,
            sha256=args.sha256,
            size_bytes=args.size_bytes,
        )
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1


__all__ = [
    "command_args",
    "command_register_args",
    "entries_for_workflow",
    "load_final_workflow",
    "model_reconciliation_hint",
    "reconcile_workflow_models",
    "register_workflow_model",
    "sidecar_path_for_workflow",
]
