from __future__ import annotations

import argparse
import sys

from vibecomfy.cli_loader import load_bundle
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
        memory_profile = getattr(args, "memory_profile", None)
        if memory_profile is not None and args.server_url is not None:
            print(_memory_profile_restart_required_message("explicit --server-url"), file=sys.stderr)
            return 2
        schema_provider = get_schema_provider("local")
        try:
            bundle = load_bundle(
                args.path,
                schema_provider=schema_provider,
            )
            workflow = bundle.workflow
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
        # Runtime/receipt transport is T14-owned.  Do not pass this mutable
        # candidate to the legacy bare-workflow runtime while that handoff is
        # unavailable; compile only through the canonical approval seam and
        # fail closed rather than silently authorizing a second path.
        try:
            bundle.compile(schema_provider=schema_provider)
        except Exception as exc:
            print(f"run failed: {exc}", file=sys.stderr)
            return 1
        print(
            "run failed: approved-record runtime transport is not available; "
            "use the T14 runtime boundary before executing this workflow",
            file=sys.stderr,
        )
        return 1
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return 1
        return 1


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
