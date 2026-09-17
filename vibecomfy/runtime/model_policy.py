from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibecomfy.workflow import VibeWorkflow

RuntimeModelMode = Literal[
    "embedded",
    "managed_local_server",
    "attached_local_session_verified",
    "explicit_remote_server_shared_root",
    "explicit_remote_server_unverified",
]


@dataclass(frozen=True)
class ModelPreflightPolicy:
    mode: RuntimeModelMode
    ensure_models: bool
    local_models_root: str
    shared_models_root: str | None = None


def normalized_models_root(path: str | Path | None = None) -> str:
    if path is None:
        from vibecomfy import fetch as fetch_assets

        path = fetch_assets.models_root()
    return str(Path(path).expanduser().resolve(strict=False))


def shared_models_root(cli_value: str | Path | None = None) -> str | None:
    value = cli_value if cli_value is not None else os.environ.get("VIBECOMFY_SHARED_MODELS_ROOT")
    if value is None or str(value).strip() == "":
        return None
    return normalized_models_root(value)


def resolve_model_preflight_policy(
    *,
    mode: RuntimeModelMode,
    ensure_models: bool,
    shared_root: str | Path | None = None,
    local_models_root: str | Path | None = None,
) -> ModelPreflightPolicy:
    local_root = normalized_models_root(local_models_root)
    shared = shared_models_root(shared_root)
    if mode == "explicit_remote_server_unverified":
        if ensure_models:
            if shared is None:
                raise RuntimeError(
                    "explicit remote --ensure-models requires --shared-models-root or VIBECOMFY_SHARED_MODELS_ROOT"
                )
            if shared != local_root:
                raise RuntimeError(
                    "explicit remote --ensure-models requires shared models root to match local models root "
                    f"({shared!r} != {local_root!r})"
                )
            return ModelPreflightPolicy(
                mode="explicit_remote_server_shared_root",
                ensure_models=True,
                local_models_root=local_root,
                shared_models_root=shared,
            )
        return ModelPreflightPolicy(mode=mode, ensure_models=False, local_models_root=local_root, shared_models_root=shared)
    return ModelPreflightPolicy(mode=mode, ensure_models=ensure_models, local_models_root=local_root, shared_models_root=shared)


def ensure_workflow_models(
    workflow: VibeWorkflow, *, models_root: str | Path | None = None
) -> None:
    from vibecomfy import fetch as fetch_assets
    from vibecomfy.runtime.session import _model_assets_from_workflow

    root = Path(normalized_models_root(models_root)) if models_root is not None else None
    entries = _model_assets_from_workflow(workflow, models_root=root)
    if entries:
        try:
            downloadable = [
                entry for entry in entries
                if isinstance(entry.get("url"), str) and entry["url"].strip()
            ]
            if downloadable:
                try:
                    fetch_assets.download_many(downloadable, root=root)
                except TypeError as exc:
                    # Preserve the small, pre-existing fetch seam used by
                    # embedders while the optional destination-root argument
                    # rolls out.  Do not mask ordinary downloader failures.
                    if "root" not in str(exc):
                        raise
                    fetch_assets.download_many(downloadable)
        except Exception as exc:
            raise RuntimeError(f"ensure_models: {exc}") from exc


def apply_model_preflight(workflow: VibeWorkflow, policy: ModelPreflightPolicy) -> None:
    if policy.ensure_models:
        ensure_workflow_models(workflow, models_root=policy.local_models_root)
