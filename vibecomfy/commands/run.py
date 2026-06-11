from __future__ import annotations

import argparse
import sys
from typing import Any

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.registry.library import load_workflow_reference
from vibecomfy.runtime.model_policy import (
    apply_model_preflight,
    normalized_models_root,
    resolve_model_preflight_policy,
    shared_models_root,
)
from vibecomfy.runtime.run import run_embedded_sync, run_sync
from vibecomfy.runtime.session import SessionConfig, active_session_metadata, apply_memory_profile_override, find_active_session
from vibecomfy.schema import get_schema_provider


_OVERRIDE_HINTS = {
    "prompt": (
        "--prompt is only wired when the workflow contains a known mainline prompt encoder "
        "(see vibecomfy.metadata.PROMPT_NODE_CLASSES). Edit the source workflow's prompt "
        "fields directly, or extend PROMPT_NODE_CLASSES if a custom-node class genuinely "
        "accepts a free-form image prompt."
    ),
    "steps": (
        "--steps is only wired when the workflow contains a known mainline sampler "
        "(see vibecomfy.metadata.STEPS_NODE_CLASSES). Edit the source workflow's sampler "
        "step count directly, or extend STEPS_NODE_CLASSES if a custom-node class exposes "
        "a true sample-step count."
    ),
    "seed": (
        "--seed is only wired when the workflow registers a public seed input. "
        "Edit the source workflow's seed fields directly, or register the seed input "
        "with bind_input()/InputSpec before using the universal CLI override."
    ),
}


def _override_unwired_message(workflow_id: str, flag: str, override: str) -> str:
    hint = _OVERRIDE_HINTS[override]
    return (
        f"run failed: workflow {workflow_id!r} has no eligible target for {flag}. {hint}"
    )


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        ensure_packs = bool(getattr(args, "ensure_packs", False))
        ensure_models_flag = getattr(args, "ensure_models", None)
        ensure_models_requested = ensure_models_flag is True
        ensure_models_disabled = ensure_models_flag is False
        memory_profile = getattr(args, "memory_profile", None)
        session_url = args.server_url
        session_metadata = None
        if memory_profile is not None and args.server_url is not None:
            print(_memory_profile_restart_required_message("explicit --server-url"), file=sys.stderr)
            return 2
        if session_url is None and args.runtime in {"auto", "server"}:
            session_metadata = active_session_metadata("default")
            session_url = str(session_metadata["url"]) if session_metadata else find_active_session("default")
            if memory_profile is not None and session_url is not None:
                print(_memory_profile_restart_required_message("already-running session"), file=sys.stderr)
                return 2
        schema_provider = get_schema_provider("auto", server_url=session_url)
        try:
            workflow = load_workflow_reference(
                args.path,
                schema_provider=schema_provider,
                allow_scratchpad=True,
                ready=args.ready,
            )
        except SyntaxError as exc:
            print(f"run failed: SyntaxError: {exc}", file=sys.stderr)
            return 1
        if args.prompt is not None:
            if workflow.inputs.get("prompt") is None:
                print(_override_unwired_message(workflow.id, "--prompt", "prompt"), file=sys.stderr)
                return 2
            workflow.set_prompt(args.prompt)
        if args.seed is not None:
            if workflow.inputs.get("seed") is None:
                print(_override_unwired_message(workflow.id, "--seed", "seed"), file=sys.stderr)
                return 2
            workflow.set_seed(args.seed)
        if args.steps is not None:
            if workflow.inputs.get("steps") is None:
                print(_override_unwired_message(workflow.id, "--steps", "steps"), file=sys.stderr)
                return 2
            workflow.set_steps(args.steps)
        override_config = None
        if memory_profile is not None:
            override_config = apply_memory_profile_override(
                SessionConfig.from_workflow_metadata(workflow),
                memory_profile,
            )
        quiet_schema_degradation = bool(getattr(args, "quiet_schema_degradation", False))
        if quiet_schema_degradation:
            base_config = override_config or SessionConfig.from_workflow_metadata(workflow)
            base_config.extra["quiet_schema_degradation"] = True
            override_config = base_config
        if args.runtime == "embedded":
            ensure_models = not ensure_models_disabled
            if override_config is None:
                result = _run_embedded_command(workflow, backend=args.backend, ensure_packs=ensure_packs, ensure_models=ensure_models)
            else:
                result = _run_embedded_command(workflow, backend=args.backend, config=override_config, ensure_packs=ensure_packs, ensure_models=ensure_models)
        elif args.runtime == "auto":
            if session_url:
                if ensure_packs:
                    print("run failed: --ensure-packs is only supported for embedded runtime", file=sys.stderr)
                    return 2
                ensure_models = _server_ensure_models_enabled(
                    ensure_models_requested=ensure_models_requested,
                    ensure_models_disabled=ensure_models_disabled,
                    explicit_server_url=args.server_url is not None,
                )
                if args.server_url is None and session_metadata is None and not ensure_models_requested:
                    ensure_models = False
                shared_root = shared_models_root(getattr(args, "shared_models_root", None))
                if ensure_models and args.server_url is None:
                    policy = _active_session_policy(session_metadata, shared_root=shared_root)
                    apply_model_preflight(workflow, policy)
                    ensure_models = False
                result = _run_server_command(
                    workflow,
                    server_url=session_url,
                    backend=args.backend,
                    ensure_models=ensure_models,
                    shared_models_root=shared_root,
                )
            else:
                ensure_models = not ensure_models_disabled
                if override_config is None:
                    result = _run_embedded_command(workflow, backend=args.backend, ensure_packs=ensure_packs, ensure_models=ensure_models)
                else:
                    result = _run_embedded_command(workflow, backend=args.backend, config=override_config, ensure_packs=ensure_packs, ensure_models=ensure_models)
        elif args.runtime == "server":
            if ensure_packs:
                print("run failed: --ensure-packs is only supported for embedded runtime", file=sys.stderr)
                return 2
            ensure_models = _server_ensure_models_enabled(
                ensure_models_requested=ensure_models_requested,
                ensure_models_disabled=ensure_models_disabled,
                explicit_server_url=args.server_url is not None,
            )
            if args.server_url is None and session_url is not None and session_metadata is None and not ensure_models_requested:
                ensure_models = False
            shared_root = shared_models_root(getattr(args, "shared_models_root", None))
            if ensure_models and args.server_url is None and session_url is not None:
                policy = _active_session_policy(session_metadata, shared_root=shared_root)
                apply_model_preflight(workflow, policy)
                ensure_models = False
            if override_config is None:
                result = _run_server_command(
                    workflow,
                    server_url=session_url,
                    backend=args.backend,
                    ensure_models=ensure_models,
                    shared_models_root=shared_root,
                )
            else:
                result = _run_server_command(
                    workflow,
                    server_url=session_url,
                    backend=args.backend,
                    config=override_config,
                    ensure_models=ensure_models,
                    shared_models_root=shared_root,
                )
        else:
            print(f"unknown runtime: {args.runtime}", file=sys.stderr)
            return 2
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return 1
    print(f"run_id: {result.run_id}")
    print(f"prompt_id: {result.prompt_id}")
    for output in result.outputs:
        print(f"output: {output}")
    print(f"metadata: {result.metadata_path}")
    print(f"log: {result.log_path}")
    return 0


def _run_embedded_command(
    workflow,
    *,
    backend: str,
    config: SessionConfig | None = None,
    ensure_packs: bool = False,
    ensure_models: bool = False,
):
    kwargs: dict[str, Any] = {"backend": backend}
    if config is not None:
        kwargs["config"] = config
    if ensure_packs:
        kwargs["ensure_packs"] = True
    if ensure_models:
        kwargs["ensure_models"] = True
    return run_embedded_sync(workflow, **kwargs)


def _run_server_command(
    workflow,
    *,
    server_url: str | None,
    backend: str,
    config: SessionConfig | None = None,
    ensure_models: bool = False,
    shared_models_root: str | None = None,
):
    kwargs: dict[str, Any] = {"server_url": server_url, "backend": backend}
    if config is not None:
        kwargs["config"] = config
    if ensure_models:
        kwargs["ensure_models"] = True
    if shared_models_root is not None:
        kwargs["shared_models_root"] = shared_models_root
    return run_sync(workflow, **kwargs)


def _server_ensure_models_enabled(
    *,
    ensure_models_requested: bool,
    ensure_models_disabled: bool,
    explicit_server_url: bool,
) -> bool:
    if ensure_models_disabled:
        return False
    if explicit_server_url:
        return ensure_models_requested
    return not ensure_models_disabled


def _active_session_policy(session_metadata: dict[str, Any] | None, *, shared_root: str | None):
    local_root = session_metadata.get("models_root_normalized") if session_metadata else None
    if not local_root:
        return resolve_model_preflight_policy(
            mode="explicit_remote_server_unverified",
            ensure_models=True,
            shared_root=shared_root,
        )
    caller_root = normalized_models_root()
    if str(local_root) != caller_root:
        raise RuntimeError(
            "active session model root does not match caller local model root "
            f"({local_root!r} != {caller_root!r})"
        )
    return resolve_model_preflight_policy(
        mode="attached_local_session_verified",
        ensure_models=True,
        local_models_root=local_root,
        shared_root=shared_root,
    )


def _memory_profile_restart_required_message(target: str) -> str:
    return (
        "run failed: --memory-profile requires a new local VibeComfy runtime for this run; "
        f"cannot apply it to {target}. Stop/restart the session with `vibecomfy session start "
        "--memory-profile N`, or run without --server-url and without an active session."
    )


def register(subparsers) -> None:
    run = subparsers.add_parser("run")
    run.add_argument("path")
    run.add_argument("--ready", action="store_true")
    run.add_argument("--runtime", choices=["auto", "embedded", "server"], default="auto")
    run.add_argument("--server-url")
    run.add_argument("--backend", default="api")
    run.add_argument("--prompt")
    run.add_argument("--seed", type=int)
    run.add_argument("--steps", type=int)
    run.add_argument("--memory-profile", type=int, choices=[1, 2, 3, 4, 5])
    run.add_argument("--ensure-packs", action="store_true")
    run.add_argument("--ensure-models", dest="ensure_models", action="store_true", default=None)
    run.add_argument("--no-ensure-models", dest="ensure_models", action="store_false")
    run.add_argument("--shared-models-root")
    run.add_argument("--quiet-schema-degradation", action="store_true", help="Downgrade schema-unavailable runtime logs from ERROR to WARNING.")
    run.set_defaults(func=_cmd_run)
