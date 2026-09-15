"""Import a ComfyUI workflow into a canonical, inspectable work folder."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


def _folder_name(source: Path) -> str:
    """Make a predictable, portable folder/workflow identity from the stem."""
    name = re.sub(r"[^\w.-]+", "-", source.stem, flags=re.UNICODE).strip(".-_")
    return name or "workflow"


def _folder_name_from_reference(reference: str) -> str:
    """Derive a local bundle name from a Hivemind evidence reference."""
    from vibecomfy.porting.hivemind_source import evidence_id_for_reference

    evidence_id = evidence_id_for_reference(reference)
    if evidence_id is None:
        return "workflow"
    return _folder_name(Path(evidence_id.rsplit(":", 1)[-1]))


def _folder_name_from_url(url: str) -> str:
    from urllib.parse import urlparse

    path = urlparse(url).path.rstrip("/")
    return _folder_name(Path(path)) if path else "workflow"


def _next_commands(folder: str | Path, *, project: str | None = None) -> dict[str, str]:
    quoted_folder = shlex.quote(str(folder))
    project_option = f" --project {shlex.quote(project)}" if project else ""
    return {
        "targets": f"vibecomfy edit {quoted_folder}{project_option} targets",
        "set": f"vibecomfy edit {quoted_folder}{project_option} set <target>.<field> <JSON_VALUE>",
        "validate": f"vibecomfy validate {quoted_folder}",
        "node": "vibecomfy node <ClassType>",
    }


def _emit(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return
    if payload.get("status") == "error":
        print(f"Import failed: {payload.get('message', 'conversion failed')}", file=sys.stderr)
        if payload.get("task_id"):
            print(f"  Astrid task: {payload['task_id']} (stage: {payload.get('stage', 'unknown')})", file=sys.stderr)
            astrid = payload.get("astrid_outputs", {})
            if isinstance(astrid, dict):
                print(f"  Astrid outputs: {astrid.get('status', 'unknown')}", file=sys.stderr)
                if astrid.get("report_digest"):
                    print(f"  report digest: {astrid['report_digest']}", file=sys.stderr)
            print(f"  local publication: {payload.get('local_publication', 'unknown')}", file=sys.stderr)
            if payload.get("recovery"):
                print(f"  recover: {payload['recovery']}", file=sys.stderr)
        return
    if payload.get("status") == "preview":
        print(f"Would import {payload['source']} into {payload['folder']}/")
    else:
        print(f"Imported workflow into {payload['folder']}/")
    for label, key in (("Python", "python"), ("Companion", "companion"), ("Source", "source_copy")):
        if payload.get(key):
            print(f"  {label}: {payload[key]}")
    if payload.get("report_digest"):
        print(f"  Astrid origin report digest: {payload['report_digest']}")
    if payload.get("status") == "preview":
        return

    folder = payload["folder"]
    tracking = payload.get("tracking", {})
    tracking_mode = tracking.get("mode", "untracked") if isinstance(tracking, dict) else "untracked"
    next_commands = payload.get("next")
    if not isinstance(next_commands, dict):
        project = tracking.get("project_id") if isinstance(tracking, dict) and tracking_mode == "astrid" else None
        next_commands = _next_commands(folder, project=project)
    print(f"  tracking: {tracking_mode}")
    task_id = payload.get("task_id")
    if task_id:
        print(f"  task: {task_id}")
        print(f"  history: astrid tasks show {task_id}; astrid tasks events {task_id}")
    print("Edit the Python file directly or use the typed workflow edit commands.")
    print("Find targets and node schemas:")
    print(f"  {next_commands.get('targets', '')}")
    print(f"  {next_commands.get('node', 'vibecomfy node <ClassType>')}")
    print("Edit, then validate:")
    print(f"  {next_commands.get('set', _next_commands(folder)['set'])}")
    print(f"  {next_commands.get('validate', _next_commands(folder)['validate'])}")
    print("Editing guide: https://github.com/peteromallet/VibeComfy/blob/main/docs/guides/workflow-onboarding.md")
    diagnostics = payload.get("diagnostics", [])
    if diagnostics:
        if payload.get("report_digest"):
            print(f"Conversion reported {len(diagnostics)} diagnostic(s); the task report is available as {payload['report_digest']}.")
        else:
            print(f"Conversion reported {len(diagnostics)} diagnostic(s); inspect the JSON result or run doctor.")


def _cmd_import(args: argparse.Namespace) -> int:
    source_reference = str(args.source)
    from vibecomfy.porting.hivemind_source import (
        evidence_id_for_reference,
        fetch_hivemind_source,
    )
    from vibecomfy.porting.remote_source import is_http_url, fetch_remote_source

    hivemind_reference = evidence_id_for_reference(source_reference)
    remote_url = source_reference if is_http_url(source_reference) else None
    source = None if hivemind_reference or remote_url else Path(args.source).expanduser()
    if source is not None and not source.is_file():
        _emit({"status": "error", "message": f"Source workflow is not a file: {source}"}, json_output=args.json)
        return 1
    if (hivemind_reference or remote_url) and args.project:
        _emit(
            {
                "status": "error",
                "message": "--project is currently supported for local files; pull the Hivemind source first, then track the local bundle.",
            },
            json_output=args.json,
        )
        return 1

    if source is not None:
        workflow_id = _folder_name(source)
    elif hivemind_reference:
        workflow_id = _folder_name_from_reference(source_reference)
    else:
        workflow_id = _folder_name_from_url(source_reference)

    destination = (
        Path(args.out).expanduser()
        if args.out
        else Path.cwd() / "workflows" / workflow_id
    )
    if destination.is_symlink():
        _emit({"status": "error", "folder": str(destination), "message": f"Destination is a symbolic link: {destination}. Choose another directory with --out."}, json_output=args.json)
        return 1
    destination = destination.resolve()
    if destination.exists():
        _emit({"status": "error", "folder": str(destination), "message": f"Destination already exists: {destination}. Choose another directory with --out."}, json_output=args.json)
        return 1

    source_provenance: dict[str, Any] | None = None
    if hivemind_reference:
        try:
            resolved = fetch_hivemind_source(source_reference)
            source_bytes = resolved.source_bytes
            source_provenance = resolved.provenance
        except Exception as exc:
            _emit(
                {"status": "error", "folder": str(destination), "source": source_reference, "message": f"{type(exc).__name__}: {exc}"},
                json_output=args.json,
            )
            return 1
    elif remote_url:
        try:
            resolved = fetch_remote_source(remote_url)
            source_bytes = resolved.source_bytes
            source_provenance = resolved.provenance
        except Exception as exc:
            _emit(
                {"status": "error", "folder": str(destination), "source": source_reference, "message": f"{type(exc).__name__}: {exc}"},
                json_output=args.json,
            )
            return 1
    else:
        try:
            source_bytes = source.read_bytes()
        except OSError as exc:
            _emit({"status": "error", "folder": str(destination), "message": str(exc)}, json_output=args.json)
            return 1

    if args.project and not args.dry_run:
        try:
            payload = _tracked_import(args, source, source_bytes, destination)
        except Exception as exc:
            from vibecomfy.commands._astrid_workflows import TrackedWorkflowFailure

            if isinstance(exc, TrackedWorkflowFailure):
                payload = exc.to_payload()
                payload["folder"] = str(destination)
                _emit(payload, json_output=args.json)
                return 1
            _emit({"status": "error", "folder": str(destination), "message": f"{type(exc).__name__}: {exc}"}, json_output=args.json)
            return 1
        _emit(payload, json_output=args.json)
        return 0

    try:
        from vibecomfy.porting.import_service import import_workflow_bytes

        artifacts = import_workflow_bytes(
            source_bytes,
            workflow_id=workflow_id,
            source_provenance=source_provenance,
        )
    except Exception as exc:
        _emit({"status": "error", "folder": str(destination), "message": f"{type(exc).__name__}: {exc}"}, json_output=args.json)
        return 1

    python_path = destination / "workflow.py"
    companion_path = destination / "workflow.vibe.json"
    source_copy_path = destination / "source.json"
    report = artifacts.report
    diagnostics = report.get("diagnostics", [])
    tracking_mode = (
        {"mode": "astrid_preview", "astrid": False, "project": args.project}
        if args.project
        else {"mode": "untracked", "astrid": False}
    )
    payload = {
        "status": "preview" if args.dry_run else "ok",
        "tracking": tracking_mode,
        "source": str(source.resolve()) if source is not None else source_reference,
        "folder": str(destination),
        "python": str(python_path),
        "companion": str(companion_path),
        "source_copy": str(source_copy_path),
        "workflow_id": report.get("workflow_id"),
        "revision": report.get("revision_id"),
        "members": report.get("members"),
        "report": report,
        "readiness": report.get("readiness"),
        "diagnostics": diagnostics if isinstance(diagnostics, list) else [],
        "next": {
            **_next_commands(destination, project=args.project),
        "tracking": (
            f"preview only; would record this import in Astrid project {args.project}"
            if args.project
            else "untracked; pass --project <project> to record this import in Astrid"
        ),
        },
    }
    if hivemind_reference:
        payload["source_reference"] = hivemind_reference
    elif remote_url:
        payload["source_reference"] = remote_url
    if args.dry_run:
        _emit(payload, json_output=args.json)
        return 0

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.import-", dir=destination.parent))
    except OSError as exc:
        _emit({"status": "error", "folder": str(destination), "message": str(exc)}, json_output=args.json)
        return 1

    try:
        (staging / "workflow.py").write_bytes(artifacts.python_bytes)
        (staging / "workflow.vibe.json").write_bytes(artifacts.companion_bytes)
        (staging / "source.json").write_bytes(artifacts.source_bytes)
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}. Choose another directory with --out.")
        os.rename(staging, destination)
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        _emit({"status": "error", "folder": str(destination), "message": str(exc)}, json_output=args.json)
        return 1

    _emit(payload, json_output=args.json)
    return 0


def _tracked_import(args: argparse.Namespace, source: Path, source_bytes: bytes, destination: Path) -> dict[str, Any]:
    """Admit origin through Astrid, then materialize only settled outputs."""
    from vibecomfy.commands._astrid_workflows import (
        create_task,
        digest_bytes,
        download_outputs,
        materialize_outputs,
        open_client,
        report_for_outputs,
        resolve_project,
        save_receipt,
        settled_output_digests,
        stable_idempotency_key,
        track_admitted_task,
        upload_bytes,
        wait_for_task,
    )

    workflow_id = _folder_name(source)
    client = open_client()
    project_id = resolve_project(client, args.project)
    source_digest = digest_bytes(source_bytes)
    upload = upload_bytes(
        client,
        project_id,
        "source",
        source_bytes,
        filename="source.json",
        key=stable_idempotency_key("vibecomfy-media-", {"project_id": project_id, "name": "source", "digest": source_digest}),
    )
    request = {"project_id": project_id, "workflow_id": workflow_id, "source_digest": source_digest}
    idempotency_key = stable_idempotency_key("vibecomfy-import-", request)
    task_id = create_task(
        client,
        project_id=project_id,
        capability="vibecomfy.import",
        workflow_id=workflow_id,
        transition_kind="origin",
        uploads=[upload],
        idempotency_key=idempotency_key,
    )
    with track_admitted_task(task_id, destination) as progress:
        receipt = {
            "schema_version": 1,
            "task_id": task_id,
            "project_id": project_id,
            "project": args.project,
            "workflow_id": workflow_id,
            "transition_kind": "origin",
            "idempotency_key": idempotency_key,
            "target_path": str(destination),
            "parent_members": None,
            "outputs": {},
            "report_digest": None,
            "input_digests": {"source": source_digest},
        }
        save_receipt(receipt)
        progress.stage = "task_settlement"
        task = wait_for_task(client, task_id)
        settled = settled_output_digests(task)
        progress.astrid_outputs = "settled"
        progress.report_digest = settled.get("report")
        progress.output_digests = {
            output_name: settled[name]
            for output_name, name in (
                ("workflow.py", "python"),
                ("workflow.vibe.json", "companion"),
                ("source.json", "source"),
            )
            if name in settled
        }
        progress.stage = "output_download"
        _task_id, outputs, manifest = download_outputs(
            client,
            task,
            expected_names={"python", "companion", "source", "report"},
        )
        progress.report_digest = manifest.get("report")
        progress.output_digests = {
            "workflow.py": manifest["python"],
            "workflow.vibe.json": manifest["companion"],
            "source.json": manifest["source"],
        }
        if outputs["source"] != source_bytes:
            raise ValueError("Astrid import output source.json differs from the exact source bytes")
        progress.stage = "report_validation"
        report = report_for_outputs(
            outputs,
            manifest,
            workflow_id=workflow_id,
            transition_kind="origin",
            parent_revision=None,
            parent_task_id=None,
            origin_task_id=None,
        )
        members = dict(progress.output_digests)
        receipt.update({
            "outputs": members,
            "report_digest": manifest["report"],
            "revision_id": report.get("revision_id"),
        })
        progress.stage = "settled_receipt"
        save_receipt(receipt)
        progress.stage = "local_publication"
        progress.local_publication = "in_progress"
        materialize_outputs(outputs, destination)
        progress.local_publication = "published"
        progress.stage = "final_receipt"
        save_receipt(receipt)
    return {
        "status": "ok",
        "tracking": {"mode": "astrid", "astrid": True, "project_id": project_id},
        "source": str(source.resolve()),
        "folder": str(destination),
        "python": str(destination / "workflow.py"),
        "companion": str(destination / "workflow.vibe.json"),
        "source_copy": str(destination / "source.json"),
        "workflow_id": workflow_id,
        "revision": report.get("revision_id"),
        "task_id": task_id,
        "report_digest": manifest["report"],
        "members": members,
        "report": report,
        "readiness": report.get("readiness"),
        "diagnostics": report.get("diagnostics", []),
        "next": {
            **_next_commands(destination, project=project_id),
            "tracking": f"tracked by task {task_id}",
            "history": f"astrid tasks show {task_id}; astrid tasks events {task_id}",
        },
    }


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "import",
        help="Import a ComfyUI workflow into an editable, inspectable folder.",
        description=(
            "Import a local ComfyUI JSON file, public HTTP(S) URL, or one Hivemind workflow reference into\n"
            "./workflows/<name>/ with an editable Python workflow, VibeComfy companion,\n"
            "and exact source copy. The origin report is returned on stdout/JSON; tracked\n"
            "local imports also retain the immutable Astrid task report."
        ),
        epilog=(
            "Edit workflow.py directly or use `vibecomfy edit`; inspect node definitions with\n"
            "`vibecomfy node <ClassType>` and validate changes with `vibecomfy validate <folder>`.\n"
            "Use a public `https://...` URL or `hivemind:external_resources:<id>` (or `hivemind://resource/<id>`;\n"
            "append `/revisions/<revision>` when the returned row exposes one) to\n"
            "pull one public workflow on demand. Imports are local and untracked unless\n"
            "you explicitly pass --project for a local file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        help="Source local JSON file, public HTTP(S) URL, or Hivemind reference (optionally /revisions/<revision>).",
    )
    parser.add_argument("--out", help="Destination directory (defaults to ./workflows/<source-name>/).")
    parser.add_argument("--project", help="Opt into recording this import as an Astrid workflow origin.")
    parser.add_argument("--dry-run", action="store_true", help="Build a preview without writing files or contacting Astrid.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable result.")
    parser.set_defaults(func=_cmd_import)
