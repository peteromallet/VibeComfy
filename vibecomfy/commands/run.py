from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
import uuid
from pathlib import Path

from vibecomfy.cli_loader import load_bundle
from vibecomfy.workflow_bundle import WorkflowAuthorityError, WorkflowBundleError
from vibecomfy.runtime.run import run_embedded_sync, run_sync
from vibecomfy.runtime.session import SessionConfig, active_session_metadata, find_active_session
from vibecomfy.runtime.session_binding import load_binding
from vibecomfy.runtime.prepared import PreparationError, prepare_workflow
from vibecomfy.registry.static_contract import reconcile_ready_template_file
from vibecomfy.schema import get_authoring_schema_provider, get_target_schema_provider
from vibecomfy.utils import atomic_write_json


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


def _persist_cli_dependency_failure(
    *,
    workflow: object,
    runtime_requirements: object,
    runtime_report: dict[str, object],
    runtime_root: str | Path | None,
    phase: str,
    error: BaseException,
) -> Path | None:
    """Persist a pre-queue CLI dependency failure before a run record exists."""
    try:
        root = Path(runtime_root).expanduser() if runtime_root is not None else Path.cwd()
        run_id = f"dependency-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        run_dir = root / "out" / "dependency-failures" / run_id
        report = dict(runtime_report)
        report.setdefault("changes", [])
        report["error"] = str(error)
        payload = {
            "receipt_type": "runtime_dependency_failure",
            "run_id": run_id,
            "workflow_id": getattr(workflow, "id", None),
            "phase": phase,
            "status": "failed",
            "requirements": getattr(runtime_requirements, "to_dict", lambda: {})(),
            "runtime_dependency": report,
            "managed_runtime": {
                "runtime_root": str(root.resolve(strict=False)),
                "artifact_location": str(run_dir),
            },
            "log_provenance": {
                "available": False,
                "kind": "not_started",
                "path": None,
            },
        }
        return atomic_write_json(run_dir / "receipt.json", payload)
    except (OSError, TypeError, ValueError):
        return None


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        ensure_packs = bool(getattr(args, "ensure_packs", False))
        session_id = getattr(args, "session", None)
        runtime_root = getattr(args, "runtime_root", None)
        memory_profile = getattr(args, "memory_profile", None)
        runtime = getattr(args, "runtime", "auto")
        server_url = getattr(args, "server_url", None)
        dependency_mode = getattr(args, "deps", "reuse")
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
        bound_target = load_binding(lookup_session_id, runtime_root)
        bound_lifecycle_adapter = None
        if isinstance(bound_target, dict) and bound_target.get("remote") is True:
            from vibecomfy.commands.runpod import BoundRunPodLifecycleAdapter

            bound_lifecycle_adapter = BoundRunPodLifecycleAdapter(
                bound_target,
                session_id=lookup_session_id,
            )
        if session_url is None and runtime in {"auto", "server"}:
            session_metadata = active_session_metadata(lookup_session_id, runtime_root=runtime_root)
            session_url = (
                str(session_metadata["url"])
                if session_metadata
                else _find_session(lookup_session_id, runtime_root)
            )
            if session_url is None and isinstance(bound_target, dict):
                bound_url = (
                    bound_target.get("comfy_url")
                    or bound_target.get("url")
                    or bound_target.get("endpoint")
                )
                if isinstance(bound_url, str) and bound_url.strip():
                    session_url = bound_url.strip().rstrip("/")
                    session_metadata = {
                        "url": session_url,
                        "source": "vibecomfy_runpod_binding",
                        "config": {
                            "runtime_root": bound_target.get("comfy_root") or runtime_root,
                            "launch_flags": list(bound_target.get("launch_flags") or []),
                            "comfy_root": bound_target.get("comfy_root"),
                            "python_executable": bound_target.get("python_executable"),
                            "custom_nodes_root": bound_target.get("custom_nodes_root"),
                            "models_root": bound_target.get("models_root"),
                        },
                        "binding": dict(bound_target),
                    }
            if memory_profile is not None and session_url is not None:
                print(_memory_profile_restart_required_message("already-running session"), file=sys.stderr)
                return 2
        if session_id and runtime in {"auto", "server"} and session_url is None:
            if isinstance(bound_target, dict):
                print(
                    f"run failed: named RunPod binding {session_id!r} has no comfy_url/endpoint; "
                    "record a reachable endpoint with `vibecomfy runpod bind --comfy-url ...`",
                    file=sys.stderr,
                )
                return 2
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
                allow_unresolved=True,
            )
            if not bool(getattr(bundle, "is_unresolved", False)):
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
        from vibecomfy.runtime.dependencies import (
            RuntimeDependencyError,
            compare_runtime,
            inspect_runtime_target,
            runtime_requirements_from_workflow,
            sync_runtime,
        )
        runtime_requirements = runtime_requirements_from_workflow(workflow)
        runtime_dependency_report = None
        if runtime_requirements is not None:
            if server_url is not None:
                # An explicit server owns its interpreter and filesystem. A
                # local process observation must never masquerade as its facts.
                runtime_dependency_report = compare_runtime(
                    runtime_requirements, target={}, runtime_root=None
                )
            elif session_url is not None:
                session_config = (session_metadata or {}).get("config", {})
                target_root = (
                    session_config.get("runtime_root")
                    if isinstance(session_config, dict)
                    else None
                ) or runtime_root or Path.cwd()
                target = inspect_runtime_target(
                    runtime_root=target_root,
                    package_names=[name for name, _constraint in runtime_requirements.packages],
                )
                if isinstance(session_config, dict) and isinstance(session_config.get("launch_flags"), list):
                    target["launch_flags"] = list(session_config["launch_flags"])
                target["runtime_root"] = str(target_root)
                target["managed"] = True
                runtime_dependency_report = compare_runtime(
                    runtime_requirements, target=target, runtime_root=target_root
                )
            else:
                runtime_dependency_report = compare_runtime(
                    runtime_requirements,
                    runtime_root=runtime_root or Path.cwd(),
                )
            runtime_dependency_report["mode"] = dependency_mode
            runtime_dependency_report.setdefault("changes", [])

        if (
            dependency_mode == "sync"
            and session_url is not None
            and server_url is None
            and bound_lifecycle_adapter is None
        ):
            if not getattr(args, "restart_session", False):
                print(
                    "run failed: --deps sync refused while the managed session is active; "
                    "stop it or pass --restart-session",
                    file=sys.stderr,
                )
                return 1
            from vibecomfy.commands import session as session_command

            if session_command._cmd_session_stop(
                argparse.Namespace(
                    id=lookup_session_id,
                    runtime_root=runtime_root or str(Path.cwd()),
                    quiet=True,
                )
            ) != 0:
                print(f"run failed: could not safely restart session {lookup_session_id!r}", file=sys.stderr)
                return 1
            session_url = None
            session_metadata = None

        offline_sync = (
            dependency_mode == "sync"
            and os.environ.get("VIBECOMFY_OFFLINE") == "1"
        )
        if offline_sync and runtime_requirements is not None:
            offline_report = compare_runtime(
                runtime_requirements,
                runtime_root=runtime_root or Path.cwd(),
            )
            if not offline_report.get("ok") or offline_report.get("status") != "matching":
                receipt = _persist_cli_dependency_failure(
                    workflow=workflow,
                    runtime_requirements=runtime_requirements,
                    runtime_report={**offline_report, "mode": "sync"},
                    runtime_root=runtime_root,
                    phase="dependencies",
                    error=RuntimeDependencyError(
                        "offline synchronization requires an already matching runtime"
                    ),
                )
                print(
                    "run failed: --deps sync cannot repair a runtime in offline mode; "
                    "all declared dependencies must already match before preparation",
                    file=sys.stderr,
                )
                if receipt is not None:
                    print(f"dependency_receipt: {receipt}", file=sys.stderr)
                return 1

        if (
            dependency_mode == "sync"
            and runtime_requirements is not None
            and server_url is None
            and bound_lifecycle_adapter is None
        ):
            try:
                runtime_dependency_report = sync_runtime(
                    runtime_requirements,
                    runtime_root=runtime_root or Path.cwd(),
                    offline=os.environ.get("VIBECOMFY_OFFLINE") == "1",
                    launch_flags=list(runtime_requirements.launch_flags),
                )
            except RuntimeDependencyError as exc:
                receipt = _persist_cli_dependency_failure(
                    workflow=workflow,
                    runtime_requirements=runtime_requirements,
                    runtime_report=dict(getattr(exc, "dependency_report", None) or runtime_dependency_report or {}),
                    runtime_root=runtime_root,
                    phase="dependencies",
                    error=exc,
                )
                print(f"run failed: {exc}", file=sys.stderr)
                if receipt is not None:
                    print(f"dependency_receipt: {receipt}", file=sys.stderr)
                return 1
        elif dependency_mode == "sync" and server_url is not None:
            receipt = _persist_cli_dependency_failure(
                workflow=workflow,
                runtime_requirements=runtime_requirements,
                runtime_report=dict(runtime_dependency_report or {}),
                runtime_root=runtime_root,
                phase="dependencies",
                error=RuntimeDependencyError(
                    "--deps sync is unavailable for an explicit external server"
                ),
            )
            print(
                "run failed: --deps sync is non-mutating only for managed targets; "
                "an explicit external server can use --deps reuse",
                file=sys.stderr,
            )
            if receipt is not None:
                print(f"dependency_receipt: {receipt}", file=sys.stderr)
            return 2

        local_source = _canonical_source_path(args.path, workflow)
        local_prepare = (
            server_url is None
            and local_source is not None
            and bound_lifecycle_adapter is None
        )
        if (
            bound_lifecycle_adapter is not None
            and server_url is None
            and local_source is not None
        ):
            remote_target = {
                "managed": True,
                "pod_id": bound_target.get("pod_id") if isinstance(bound_target, dict) else None,
                "runtime_root": bound_target.get("comfy_root") if isinstance(bound_target, dict) else runtime_root,
                "comfy_root": bound_target.get("comfy_root") if isinstance(bound_target, dict) else None,
                "python_executable": bound_target.get("python_executable") if isinstance(bound_target, dict) else None,
                "custom_nodes_root": bound_target.get("custom_nodes_root") if isinstance(bound_target, dict) else None,
                "models_root": bound_target.get("models_root") if isinstance(bound_target, dict) else None,
                "launch_flags": list(bound_target.get("launch_flags") or []) if isinstance(bound_target, dict) else [],
            }
            try:
                preparation = prepare_workflow(
                    workflow,
                    reference=local_source or args.path,
                    runtime_root=runtime_root or Path.cwd(),
                    ensure_models=ensure_models_option is not False,
                    ensure_packs=True,
                    session_id=lookup_session_id,
                    download_workers=getattr(args, "download_workers", None),
                    quiet=bool(getattr(args, "json", False)),
                    runtime_dependency_report=runtime_dependency_report,
                    dependency_mode=dependency_mode,
                    runtime_target=remote_target,
                    offline=os.environ.get("VIBECOMFY_OFFLINE") == "1",
                    remote_adapter=bound_lifecycle_adapter,
                )
            except PreparationError as exc:
                print(f"run failed: {exc}", file=sys.stderr)
                return 1
        if local_prepare:
            try:
                reconciliation = reconcile_ready_template_file(local_source)
            except OSError as exc:
                print(f"run failed: dependency reconciliation could not read {local_source}: {exc}", file=sys.stderr)
                return 1
            dynamic_diagnostics = [
                item for item in reconciliation.get("diagnostics", [])
                if str(item.get("code", "")).startswith("static_dynamic")
                or item.get("code") == "manual_repair_required"
            ]
            blockers = list(reconciliation.get("blockers", []))
            if dynamic_diagnostics:
                blockers.extend(dynamic_diagnostics)
            if blockers:
                _print_dependency_blockers(blockers)
                return 1
            if reconciliation.get("changed"):
                try:
                    bundle = load_bundle(
                        local_source,
                        schema_provider=schema_provider,
                        allow_unresolved=True,
                    )
                    if not bool(getattr(bundle, "is_unresolved", False)):
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
                    runtime_dependency_report=runtime_dependency_report,
                )
            except PreparationError as exc:
                print(f"run failed: {exc}", file=sys.stderr)
                return 1
        runtime_requirements = runtime_requirements_from_workflow(workflow)

        bundle_unresolved = tuple(getattr(bundle, "unresolved", ()) or ())
        unresolved_non_companion = [
            item for item in bundle_unresolved if str(item.get("kind", "")) != "companion"
        ]
        if unresolved_non_companion:
            unresolved = [dict(item) for item in bundle_unresolved]
            detail = "; ".join(
                str(item.get("message", item)) for item in unresolved
            ) or "workflow requires dependency/schema reconciliation"
            error = WorkflowBundleError(
                "workflow remains an unresolved draft after dependency preparation: "
                + detail
            )
            receipt = _persist_cli_dependency_failure(
                workflow=workflow,
                runtime_requirements=runtime_requirements,
                runtime_report=dict(runtime_dependency_report or {}),
                runtime_root=runtime_root,
                phase="mapping",
                error=error,
            )
            print(f"run failed: {error}", file=sys.stderr)
            if receipt is not None:
                print(f"dependency_receipt: {receipt}", file=sys.stderr)
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
                launch_flags=list(runtime_requirements.launch_flags) if runtime_requirements is not None else None,
                quiet=True,
            )
            if session_command._cmd_session_start(start_args) != 0:
                return 1
            session_url = _find_session(lookup_session_id, start_args.runtime_root)
            started_session = session_url is not None
            session_metadata = active_session_metadata(
                lookup_session_id, runtime_root=start_args.runtime_root
            )
            if session_url is None:
                print("run failed: managed session did not become active", file=sys.stderr)
                return 1
        # Final target admission happens after the managed session is alive and
        # immediately before compilation.  The target provider is live-only;
        # the reconciler uses retained source rosters, then republishes the
        # canonical Python/companion pair transactionally when needed.
        # Reconciliation may have published and reloaded a clean canonical
        # pair. Re-read unresolved state from that execution snapshot instead
        # of carrying the pre-reconciliation tuple forward.
        bundle_unresolved = tuple(getattr(bundle, "unresolved", ()) or ())
        if bundle_unresolved:
            unresolved = [dict(item) for item in bundle_unresolved]
            detail = "; ".join(str(item.get("message", item)) for item in unresolved)
            error = WorkflowBundleError(
                "workflow remains an unresolved draft after live reconciliation: " + detail
            )
            receipt = _persist_cli_dependency_failure(
                workflow=workflow,
                runtime_requirements=runtime_requirements,
                runtime_report=dict(runtime_dependency_report or {}),
                runtime_root=runtime_root,
                phase="mapping",
                error=error,
            )
            print(f"run failed: {error}", file=sys.stderr)
            if receipt is not None:
                print(f"dependency_receipt: {receipt}", file=sys.stderr)
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
        config_extra = {
            "quiet_schema_degradation": bool(getattr(args, "quiet_schema_degradation", False)),
        }
        external_log_locator = getattr(args, "external_log_locator", None)
        if external_log_locator is not None:
            config_extra["external_log_locator"] = external_log_locator
        output_directory = getattr(args, "output_directory", None)
        if output_directory is not None:
            config_extra["output_directory"] = output_directory
        if runtime_requirements is not None and runtime_requirements.launch_flags:
            config_extra["launch_flags"] = list(runtime_requirements.launch_flags)
        config = SessionConfig(
            memory_profile=memory_profile,
            runtime_root=runtime_root,
            extra=config_extra,
        )

        managed_runtime_target = None
        if session_url is not None and server_url is None:
            binding = bound_target if isinstance(bound_target, dict) else None
            session_config = (session_metadata or {}).get("config", {})
            if isinstance(session_config, dict):
                if binding is not None:
                    managed_runtime_target = {
                        "managed": True,
                        "pod_id": binding.get("pod_id"),
                        "runtime_root": binding.get("comfy_root") or session_config.get("runtime_root"),
                        "comfy_root": binding.get("comfy_root"),
                        "python_executable": binding.get("python_executable"),
                        "custom_nodes_root": binding.get("custom_nodes_root"),
                        "models_root": binding.get("models_root"),
                        "launch_flags": list(binding.get("launch_flags") or []),
                    }
                    if binding.get("pod_id"):
                        from vibecomfy.commands.runpod import BoundRunPodLifecycleAdapter

                        managed_runtime_target["_runpod_lifecycle_adapter"] = (
                            bound_lifecycle_adapter
                            or BoundRunPodLifecycleAdapter(binding, session_id=lookup_session_id)
                        )
                else:
                    managed_runtime_target = inspect_runtime_target(
                        runtime_root=session_config.get("runtime_root") or runtime_root or Path.cwd(),
                        package_names=[name for name, _constraint in runtime_requirements.packages]
                        if runtime_requirements is not None else None,
                    )
                    if isinstance(session_config.get("launch_flags"), list):
                        managed_runtime_target["launch_flags"] = list(session_config["launch_flags"])
                    managed_runtime_target["runtime_root"] = str(
                        session_config.get("runtime_root") or runtime_root or Path.cwd()
                    )
                managed_runtime_target["managed"] = True

        def execute_once():
            if runtime == "embedded" or (runtime == "auto" and session_url is None):
                kwargs: dict[str, object] = {
                    "backend": getattr(args, "backend", "api"),
                    "ensure_packs": ensure_packs and preparation is None,
                    "ensure_models": bool(getattr(args, "ensure_models", False)) and preparation is None,
                    "config": config,
                }
                if dependency_mode != "reuse":
                    kwargs["dependency_mode"] = dependency_mode
                if runtime_dependency_report is not None:
                    kwargs["dependency_report"] = runtime_dependency_report
                return run_embedded_sync(record, bundle, **kwargs)
            kwargs = {
                "server_url": session_url,
                "backend": getattr(args, "backend", "api"),
                "schema_provider": schema_provider if session_url is not None else None,
                "ensure_models": False if preparation is not None else bool(getattr(args, "ensure_models", False)),
                "shared_models_root": getattr(args, "shared_models_root", None),
                "config": config,
                "runtime_target": managed_runtime_target,
            }
            if dependency_mode != "reuse":
                kwargs["dependency_mode"] = dependency_mode
            if runtime_dependency_report is not None:
                kwargs["dependency_report"] = runtime_dependency_report
            return run_sync(record, bundle, **kwargs)

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
                "queue_status": "accepted" if result.prompt_id else "unknown",
                "metadata_path": result.metadata_path,
                "completion_path": getattr(result, "completion_path", None),
                "log_path": getattr(result, "log_path", None),
                "log_provenance": getattr(result, "log_provenance", {}),
                "status": getattr(result, "status", "completed"),
                "media_validated": getattr(result, "media_validated", False),
                "outputs": list(getattr(result, "outputs", [])),
                "artifacts": list(getattr(result, "artifacts", [])),
                "session_id": lookup_session_id if session_url is not None else None,
                "session_url": session_url,
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            log_path = getattr(result, "log_path", None)
            log_provenance = getattr(result, "log_provenance", {})
            if log_path and isinstance(log_provenance, dict) and log_provenance.get("available") is True:
                log_line = f"log_path: {log_path}"
            elif isinstance(log_provenance, dict) and log_provenance.get("kind") == "external_server":
                log_line = "log_path: unavailable (external server owns its logs)"
            else:
                log_line = "log_path: unavailable (captured process log is unavailable)"
            lines = [
                f"status: {getattr(result, 'status', 'completed')}",
                f"queue_status: {'accepted' if result.prompt_id else 'unknown'}",
                f"media_validated: {getattr(result, 'media_validated', False)}",
                f"run_id: {result.run_id}",
                f"prompt_id: {result.prompt_id}",
                f"metadata_path: {result.metadata_path}",
                log_line,
            ]
            completion_path = getattr(result, "completion_path", None)
            if completion_path:
                lines.insert(-1, f"completion_path: {completion_path}")
            outputs = list(getattr(result, "outputs", []))
            if outputs:
                lines.append("outputs:")
                lines.extend(f"  - {path}" for path in outputs)
            artifacts = list(getattr(result, "artifacts", []))
            if artifacts:
                lines.append("artifact_locations:")
                for artifact in artifacts:
                    location = artifact.get("location") if isinstance(artifact, dict) else artifact
                    lines.append(f"  - {location}")
            print("\n".join(lines))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        completion_status = str(getattr(exc, "completion_status", ""))
        if not completion_status and getattr(exc, "output_verification", None) is not None:
            completion_status = "Failed — final output rejected"
        if getattr(args, "json", False):
            payload = {
                "status": completion_status or "Failed",
                "error": str(exc),
                "prompt_id": getattr(exc, "prompt_id", None),
                "receipt_path": getattr(exc, "receipt_path", None),
                "output_verification": getattr(exc, "output_verification", None),
                "delivery_state": getattr(exc, "delivery_state", None),
                "diagnostics": list(getattr(exc, "diagnostics", []) or []),
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 1
        if completion_status:
            print(f"status: {completion_status}", file=sys.stderr)
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
    run.add_argument(
        "--deps",
        choices=["reuse", "sync"],
        default="reuse",
        help="Reuse the declared runtime target or explicitly synchronize a managed target.",
    )
    run.add_argument(
        "--external-log-locator",
        help="Reference for logs owned by an explicit external Comfy server; never treated as captured.",
    )
    run.add_argument(
        "--output-directory",
        help="Comfy output root used to resolve returned filename/subfolder descriptors for verification and delivery.",
    )
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
