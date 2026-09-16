from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from vibecomfy.cli_loader import load_bundle
from vibecomfy.workflow_bundle import WorkflowAuthorityError
from vibecomfy.runtime.run import run_embedded_sync, run_sync
from vibecomfy.runtime.session import SessionConfig, active_session_metadata, find_active_session
from vibecomfy.runtime.prepared import PreparationError, prepare_workflow
from vibecomfy.registry.static_contract import reconcile_ready_template_file
from vibecomfy.schema import get_authoring_schema_provider, get_target_schema_provider


def get_schema_provider(prefer: str, *, server_url: str | None = None):
    """Select offline authoring or fresh target schema authority."""
    if server_url:
        return get_target_schema_provider(server_url)
    return get_authoring_schema_provider(on_demand_schemas=False)


def _find_session(id_: str, runtime_root: str | None) -> str | None:
    # Keep the old one-argument seam usable for embedders/tests that replace
    # the discovery function, while routing explicit roots through the new
    # persistent registry location.
    if runtime_root is None:
        return find_active_session(id_)
    return find_active_session(id_, runtime_root=runtime_root)


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


def _canonical_source_path(reference: str | Path, workflow: object) -> Path | None:
    """Return the authored Python source eligible for local reconciliation."""
    candidate = Path(reference)
    if candidate.is_file() and candidate.suffix.lower() == ".py":
        return candidate
    source = getattr(workflow, "source", None)
    source_path = getattr(source, "path", None)
    if isinstance(source_path, (str, Path)):
        candidate = Path(source_path)
        if candidate.suffix.lower() == ".py" and candidate.is_file():
            return candidate
    return None


def _print_dependency_blockers(blockers: list[dict[str, object]]) -> None:
    print(
        "Run blocked: dependencies unresolved. Nothing downloaded, installed, "
        "restarted, compiled, or queued.",
        file=sys.stderr,
    )
    for blocker in blockers:
        location = blocker.get("location")
        if not isinstance(location, dict):
            location = {}
        source = location.get("source_path", "<workflow>")
        line = location.get("line", "?")
        path = location.get("path", "dependency")
        message = blocker.get("message") or blocker.get("detail") or "unresolved dependency"
        print(f"{source}:{line} — {path}: {message}", file=sys.stderr)


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        ensure_packs = bool(getattr(args, "ensure_packs", False))
        session_id = getattr(args, "session", None)
        runtime_root = getattr(args, "runtime_root", None)
        memory_profile = getattr(args, "memory_profile", None)
        runtime = getattr(args, "runtime", "auto")
        server_url = getattr(args, "server_url", None)
        session_url = server_url
        session_metadata = None
        preparation = None
        started_session = False
        ensure_models_option = getattr(args, "ensure_models", None)
        if server_url is not None and (ensure_packs or ensure_models_option is True):
            print("run failed: explicit --server-url is non-mutating; local dependency preparation is unavailable", file=sys.stderr)
            return 2
        if memory_profile is not None and server_url is not None:
            print(_memory_profile_restart_required_message("explicit --server-url"), file=sys.stderr)
            return 2
        lookup_session_id = session_id or "default"
        if session_url is None and runtime in {"auto", "server"}:
            session_metadata = active_session_metadata(lookup_session_id, runtime_root=runtime_root)
            session_url = (
                str(session_metadata["url"])
                if session_metadata
                else _find_session(lookup_session_id, runtime_root)
            )
            if memory_profile is not None and session_url is not None:
                print(_memory_profile_restart_required_message("already-running session"), file=sys.stderr)
                return 2
        if session_id and runtime in {"auto", "server"} and session_url is None:
            print(
                f"run failed: named session {session_id!r} is not running; start it or use --runtime server",
                file=sys.stderr,
            )
            return 2
        if ensure_packs and (
            runtime == "server" or (runtime == "auto" and session_url is not None)
        ):
            print("run failed: --ensure-packs is only supported for embedded runtime", file=sys.stderr)
            return 2
        # Runtime execution must use the target-witnessed authoring schemas.
        # The static local node index can lag a freshly captured ComfyUI
        # object-info cache, which makes valid custom/core nodes look
        # unresolved at the final compile gate.  Use the effective URL so an
        # already-running managed session gets the same target authority as
        # the runtime queue.
        schema_provider = get_schema_provider("auto", server_url=session_url)
        try:
            bundle = load_bundle(
                args.path,
                schema_provider=schema_provider,
            )
            bundle.require_canonical_authority("workflow execution")
            workflow = bundle.workflow
        except WorkflowAuthorityError as exc:
            print(f"run failed: {exc}", file=sys.stderr)
            return 1
        except SyntaxError as exc:
            _print_source_migration_failure(args.path, f"SyntaxError: {exc}")
            return 1
        except Exception as exc:
            _print_source_migration_failure(args.path, str(exc))
            return 1

        local_source = _canonical_source_path(args.path, workflow)
        local_prepare = server_url is None and local_source is not None
        if local_prepare:
            try:
                reconciliation = reconcile_ready_template_file(local_source)
            except OSError as exc:
                print(f"run failed: dependency reconciliation could not read {local_source}: {exc}", file=sys.stderr)
                return 1
            dynamic_diagnostics = [
                item for item in reconciliation.get("diagnostics", [])
                if str(item.get("code", "")).startswith("static_dynamic")
            ]
            blockers = list(reconciliation.get("blockers", []))
            if dynamic_diagnostics:
                blockers.extend(dynamic_diagnostics)
            if blockers:
                _print_dependency_blockers(blockers)
                return 1
            if reconciliation.get("changed"):
                try:
                    bundle = load_bundle(local_source, schema_provider=schema_provider)
                    bundle.require_canonical_authority("workflow execution")
                    workflow = bundle.workflow
                except Exception as exc:
                    _print_source_migration_failure(str(local_source), str(exc))
                    return 1
            try:
                preparation = prepare_workflow(
                    workflow,
                    reference=local_source,
                    runtime_root=runtime_root or Path.cwd(),
                    ensure_models=ensure_models_option is not False,
                    ensure_packs=True,
                    session_id=lookup_session_id,
                    download_workers=getattr(args, "download_workers", None),
                    quiet=bool(getattr(args, "json", False)),
                )
            except PreparationError as exc:
                print(f"run failed: {exc}", file=sys.stderr)
                return 1

        if getattr(args, "restart_session", False) and session_url is not None:
            from vibecomfy.commands import session as session_command

            if session_command._cmd_session_stop(
                argparse.Namespace(
                    id=lookup_session_id,
                    runtime_root=runtime_root or str(Path.cwd()),
                )
            ) != 0:
                print(f"run failed: could not safely restart session {lookup_session_id!r}", file=sys.stderr)
                return 1
            session_url = None
        if runtime == "server" and session_url is None and (local_prepare or session_id):
            from vibecomfy.commands import session as session_command

            start_args = argparse.Namespace(
                id=lookup_session_id,
                runtime_root=runtime_root or str(Path.cwd()),
                port=8188,
                vram_policy=None,
                reserve_vram_gb=None,
                cache_policy=None,
                warm_policy="always",
                disable_smart_memory=False,
                memory_profile=memory_profile,
                input_directory=None,
                output_directory=None,
                temp_directory=None,
                ready_timeout_sec=None,
                quiet=True,
            )
            if session_command._cmd_session_start(start_args) != 0:
                return 1
            session_url = _find_session(lookup_session_id, start_args.runtime_root)
            started_session = session_url is not None
            if session_url is None:
                print("run failed: managed session did not become active", file=sys.stderr)
                return 1
        run_inputs: dict[str, object] = {}
        if args.prompt is not None:
            if workflow.inputs.get("prompt") is None:
                print(_override_unwired_message(workflow.id, "--prompt", "prompt"), file=sys.stderr)
                return 2
            run_inputs["prompt"] = args.prompt
        if args.seed is not None:
            if workflow.inputs.get("seed") is None:
                print(_override_unwired_message(workflow.id, "--seed", "seed"), file=sys.stderr)
                return 2
            run_inputs["seed"] = args.seed
        if args.steps is not None:
            if workflow.inputs.get("steps") is None:
                print(_override_unwired_message(workflow.id, "--steps", "steps"), file=sys.stderr)
                return 2
            run_inputs["steps"] = args.steps
        try:
            prepared_models_root = (
                str(Path(runtime_root).expanduser() / "ComfyUI" / "models")
                if preparation is not None and runtime_root is not None
                else None
            )
            record = bundle.compile(
                run_inputs=run_inputs,
                schema_provider=schema_provider,
                models_root=prepared_models_root,
            )
        except Exception as exc:
            print(f"run failed: {exc}", file=sys.stderr)
            return 1
        config = SessionConfig(
            memory_profile=memory_profile,
            runtime_root=runtime_root,
            extra={"quiet_schema_degradation": bool(getattr(args, "quiet_schema_degradation", False))},
        )

        def execute_once():
            if runtime == "embedded" or (runtime == "auto" and session_url is None):
                return run_embedded_sync(
                    record,
                    bundle,
                    backend=getattr(args, "backend", "api"),
                    ensure_packs=ensure_packs and preparation is None,
                    ensure_models=bool(getattr(args, "ensure_models", False)) and preparation is None,
                    config=config,
                )
            return run_sync(
                record,
                bundle,
                server_url=session_url,
                backend=getattr(args, "backend", "api"),
                schema_provider=schema_provider if session_url is not None else None,
                ensure_models=False if preparation is not None else bool(getattr(args, "ensure_models", False)),
                shared_models_root=getattr(args, "shared_models_root", None),
                config=config,
            )

        try:
            if session_url is not None:
                from vibecomfy.runtime.locks import resource_lock

                lock_root = Path(runtime_root).expanduser() if runtime_root is not None else Path.cwd()
                with resource_lock(lock_root / "out" / "sessions" / lookup_session_id):
                    result = execute_once()
            else:
                result = execute_once()
        finally:
            if started_session and not bool(getattr(args, "keep_warm", False)):
                from vibecomfy.commands import session as session_command

                session_command._cmd_session_stop(
                    argparse.Namespace(
                        id=lookup_session_id,
                        runtime_root=runtime_root or str(Path.cwd()),
                        quiet=bool(getattr(args, "json", False)),
                    )
                )
        if getattr(args, "json", False):
            payload = {
                "run_id": result.run_id,
                "prompt_id": result.prompt_id,
                "metadata_path": result.metadata_path,
                "log_path": result.log_path,
                "session_id": lookup_session_id if session_url is not None else None,
                "session_url": session_url,
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(
                f"run_id: {result.run_id}\n"
                f"prompt_id: {result.prompt_id}\n"
                f"metadata_path: {result.metadata_path}"
            )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return 1


def _print_source_migration_failure(path: str, detail: str) -> None:
    """Point raw/legacy sources at the single import door."""
    suffixes = Path(path).suffixes
    if suffixes and suffixes[-1] in {".json", ".py"}:
        stem = Path(path).stem
        quoted_path = shlex.quote(path)
        print(
            f"run failed: {detail}\n"
            f"Next: vibecomfy import {quoted_path}\n"
            f"Then: vibecomfy validate workflows/{shlex.quote(stem)} --json",
            file=sys.stderr,
        )
        return
    print(f"run failed: {detail}", file=sys.stderr)


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
    run.add_argument("--session", help="Named managed session to reuse.")
    run.add_argument("--keep-warm", action="store_true", help="Keep a managed session started by this run alive.")
    run.add_argument("--restart-session", action="store_true", help="Stop the named managed session before execution.")
    run.add_argument("--runtime-root", help="Explicit authority for session state, models, nodes, and artifacts.")
    run.add_argument("--download-workers", type=int, help="Number of concurrent model downloads (default: 2).")
    run.add_argument("--json", action="store_true", help="Emit structured session/run evidence.")
    run.add_argument("--quiet-schema-degradation", action="store_true", help="Downgrade schema-unavailable runtime logs from ERROR to WARNING.")
    run.set_defaults(func=_cmd_run)
