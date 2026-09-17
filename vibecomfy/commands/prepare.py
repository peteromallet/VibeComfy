from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from vibecomfy.cli_loader import load_bundle
from vibecomfy.registry.static_contract import reconcile_ready_template_file
from vibecomfy.runtime.dependencies import (
    RuntimeDependencyError,
    compare_runtime,
    inspect_runtime_target,
    runtime_requirements_from_workflow,
)
from vibecomfy.runtime.prepared import PreparationError, prepare_workflow
from vibecomfy.runtime.session import active_session_metadata, find_active_session
from vibecomfy.runtime.session_binding import load_binding
from vibecomfy.schema import get_authoring_schema_provider, get_target_schema_provider
from vibecomfy.workflow_bundle import WorkflowAuthorityError
from vibecomfy.runtime.reconciliation import ReconciliationError, reconcile_before_queue


def _source_path(reference: str, workflow: Any) -> Path | None:
    candidate = Path(reference)
    if candidate.is_file() and candidate.suffix.lower() == ".py":
        return candidate
    source = getattr(workflow, "source", None)
    path = getattr(source, "path", None)
    if isinstance(path, (str, Path)):
        candidate = Path(path)
        if candidate.is_file() and candidate.suffix.lower() == ".py":
            return candidate
    return None


def _target_for_session(session_id: str, runtime_root: str | None) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    metadata = active_session_metadata(session_id, runtime_root=runtime_root)
    url = str(metadata["url"]) if isinstance(metadata, dict) and metadata.get("url") else find_active_session(session_id, runtime_root=runtime_root)
    config = metadata.get("config", {}) if isinstance(metadata, dict) else {}
    if not isinstance(config, dict):
        config = {}
    binding = load_binding(session_id, runtime_root)
    if isinstance(binding, dict) and binding.get("remote") is True:
        bound_url = (
            binding.get("comfy_url")
            or binding.get("url")
            or binding.get("endpoint")
        )
        if url is None:
            url = (
                str(bound_url).strip().rstrip("/")
                if isinstance(bound_url, str) and bound_url.strip()
                else None
            )
        return url, binding, binding
    return url, metadata, config


def _failure_receipt(args: argparse.Namespace, workflow: Any | None, requirements: Any, report: dict[str, Any], phase: str, error: BaseException) -> Path | None:
    try:
        root = Path(args.runtime_root).expanduser().resolve(strict=False) if args.runtime_root else Path.cwd().resolve(strict=False)
        receipt_dir = root / "out" / "preparations"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(args.path).stem
        path = receipt_dir / f"{stem}-{args.session or 'one-shot'}-failure.json"
        payload = {
            "receipt_type": "workflow_preparation",
            "status": "failed",
            "workflow": getattr(workflow, "id", None),
            "reference": args.path,
            "phase": phase,
            "requirements": getattr(requirements, "to_dict", lambda: {})(),
            "runtime_dependency": dict(report),
            "error": str(error),
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path
    except (OSError, TypeError, ValueError):
        return None


def _cmd_prepare(args: argparse.Namespace) -> int:
    server_url = getattr(args, "server_url", None)
    session_id = getattr(args, "session", None)
    runtime_root = getattr(args, "runtime_root", None)
    schema_provider = get_target_schema_provider(server_url) if server_url else get_authoring_schema_provider(on_demand_schemas=False)
    workflow = None
    requirements = None
    report: dict[str, Any] = {"declared": False, "status": "unverified", "checks": [], "mismatches": [], "warnings": []}
    try:
        bundle = load_bundle(args.path, schema_provider=schema_provider, allow_unresolved=True)
        workflow = bundle.workflow
        if not bundle.is_unresolved:
            bundle.require_canonical_authority("workflow preparation")
        requirements = runtime_requirements_from_workflow(workflow)

        active_url = server_url
        session_metadata = None
        session_config: dict[str, Any] = {}
        if active_url is None and session_id:
            active_url, session_metadata, session_config = _target_for_session(session_id, runtime_root)
        lifecycle_adapter = None
        lifecycle_witness: dict[str, Any] | None = None
        if isinstance(session_metadata, dict) and session_metadata.get("remote") is True:
            from vibecomfy.commands.runpod import BoundRunPodLifecycleAdapter

            lifecycle_adapter = BoundRunPodLifecycleAdapter(
                session_metadata,
                session_id=session_id or "default",
            )
            try:
                attached = asyncio.run(lifecycle_adapter.attach())
            except Exception as exc:
                raise PreparationError(
                    f"RunPod lifecycle target admission failed: {exc}"
                ) from exc
            if not isinstance(attached, dict):
                raise PreparationError("RunPod lifecycle target admission returned an invalid witness")
            lifecycle_witness = dict(attached)
        live_schema_provider = get_target_schema_provider(active_url) if active_url else None
        target_root = (
            session_config.get("runtime_root")
            if session_config
            else runtime_root
        ) or runtime_root or Path.cwd()
        external = server_url is not None
        target = {} if external else inspect_runtime_target(
            runtime_root=target_root,
            python_executable=session_config.get("python_executable") if session_config else None,
            package_names=[name for name, _constraint in requirements.packages] if requirements else None,
        )
        if session_config and isinstance(session_config.get("launch_flags"), list):
            target["launch_flags"] = list(session_config["launch_flags"])
        target["managed"] = not external
        if lifecycle_witness is not None:
            target["runpod_lifecycle"] = dict(lifecycle_witness)
        report = compare_runtime(
            requirements,
            target=target,
            runtime_root=None if external else target_root,
        )
        report["mode"] = args.deps

        unresolved_non_companion = [
            item for item in bundle.unresolved
            if str(item.get("kind", "")) != "companion"
        ]
        if unresolved_non_companion:
            payload = {
                "ok": False,
                "status": "unresolved",
                "workflow": getattr(workflow, "id", None),
                "source_revision": workflow.metadata.get("source_revision"),
                "unresolved": [dict(item) for item in unresolved_non_companion],
                "runtime_dependency": report,
            }
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else "workflow remains an unresolved draft; dependency planning is available but execution is blocked")
            return 1

        if session_config.get("remote") is True and lifecycle_adapter is not None:
            # The local coordinator still owns draft admission, planning,
            # dependency mode, and the durable preparation receipt.  The
            # lifecycle adapter executes that same coordinator on the bound
            # target; never fall through to local model/node mutation.
            source = _source_path(args.path, workflow)
            result = prepare_workflow(
                workflow,
                reference=source or args.path,
                runtime_root=runtime_root or Path.cwd(),
                ensure_models=not args.no_models,
                ensure_packs=not args.no_packs,
                session_id=session_id,
                download_workers=args.download_workers,
                quiet=args.json,
                runtime_dependency_report=report,
                dependency_mode=args.deps,
                runtime_target=target,
                offline=args.offline or os.environ.get("VIBECOMFY_OFFLINE") == "1",
                remote_adapter=lifecycle_adapter,
            )
            payload = result.to_json()
            payload["status"] = "prepared"
            payload["runtime_dependency"] = report
            payload["binding"] = dict(session_config)
            payload["lifecycle"] = lifecycle_witness
            if active_url is None:
                payload["next_action"] = "Run the workflow through the same named RunPod session."
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else f"prepared on bound target: {result.receipt_path}")
            return 0 if report.get("ok", True) else 1

        if external:
            # An external server is always inspect/execute-only. Do not let
            # model or node preparation mutate the local checkout by accident.
            payload = {"ok": True, "status": "inspected", "workflow": workflow.id, "runtime_dependency": report}
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else "inspected external server; no local or remote mutation performed")
            return 0 if report.get("ok", True) else 1

        source = _source_path(args.path, workflow)
        if source is not None:
            reconciliation = reconcile_ready_template_file(source)
            blockers = list(reconciliation.get("blockers", []))
            if blockers:
                raise PreparationError("workflow reconciliation blocked: " + "; ".join(str(item.get("message", item)) for item in blockers))
            if reconciliation.get("changed"):
                bundle = load_bundle(source, schema_provider=schema_provider)
                workflow = bundle.workflow

        result = prepare_workflow(
            workflow,
            reference=source or args.path,
            runtime_root=target_root,
            ensure_models=not args.no_models,
            ensure_packs=not args.no_packs,
            session_id=session_id,
            download_workers=args.download_workers,
            quiet=args.json,
            runtime_dependency_report=report,
            dependency_mode=args.deps,
            runtime_target=target,
            offline=args.offline or os.environ.get("VIBECOMFY_OFFLINE") == "1",
        )
        payload = result.to_json()
        payload["runtime_dependency"] = report
        if active_url is not None:
            try:
                from vibecomfy.schema.cache import object_info_payload_checksum

                object_info = live_schema_provider.object_info() if live_schema_provider is not None else {}
                payload["schema"] = {
                    "status": "captured",
                    "digest": object_info_payload_checksum(dict(object_info)),
                    "node_count": len(object_info),
                    "server_url": active_url,
                }
                reconciliation = reconcile_before_queue(
                    bundle,
                    target_schema_provider=live_schema_provider,
                    publish=True,
                )
                bundle = reconciliation.bundle
                workflow = bundle.workflow
                payload["schema_reconciliation"] = {
                    "changed": reconciliation.changed,
                    "decisions": list(reconciliation.decisions),
                    "diagnostics": list(reconciliation.diagnostics),
                }
            except Exception as exc:
                if isinstance(exc, ReconciliationError):
                    raise PreparationError(str(exc)) from exc
                raise PreparationError(f"live schema capture failed: {exc}") from exc
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else f"prepared: {result.receipt_path}")
        return 0
    except (WorkflowAuthorityError, RuntimeDependencyError, PreparationError, OSError, ValueError) as exc:
        receipt = _failure_receipt(args, workflow, requirements, report, "preparation", exc)
        print(f"prepare failed: {exc}", file=sys.stderr)
        if receipt is not None:
            print(f"receipt: {receipt}", file=sys.stderr)
        return 1


def register(subparsers) -> None:
    prepare = subparsers.add_parser("prepare", help="Inspect and prepare workflow runtime dependencies without queueing.")
    prepare.add_argument("path")
    prepare.add_argument("--session", help="Named managed session whose target is inspected.")
    prepare.add_argument("--server-url", help="Explicit external server; inspection only.")
    prepare.add_argument("--deps", choices=("reuse", "sync"), default="reuse")
    prepare.add_argument("--runtime-root")
    prepare.add_argument("--no-models", action="store_true")
    prepare.add_argument("--no-packs", action="store_true")
    prepare.add_argument("--download-workers", type=int)
    prepare.add_argument("--offline", action="store_true")
    prepare.add_argument("--json", action="store_true")
    prepare.set_defaults(func=_cmd_prepare)
