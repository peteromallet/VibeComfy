"""Typed workflow edits, batch preview, and explicit capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


def _json_value(raw: str) -> Any:
    """Parse JSON values while keeping an unquoted CLI string convenient."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _json_object(raw: str, *, option: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"{option} must be a JSON object: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError(f"{option} must be a JSON object")
    return value


def _load_batch(path_value: str) -> list[dict[str, Any]]:
    if path_value == "-":
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(Path(path_value).expanduser().read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        version = payload.get("schema_version", 1)
        expected_revision = payload.get("expected_revision", 0)
        if version != 1:
            raise ValueError("batch schema_version must be 1")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision != 0:
            raise ValueError("expected_revision must be 0 for a new atomic bundle edit")
        payload = payload.get("ops")
    if not isinstance(payload, list) or not payload:
        raise ValueError("batch input must be a non-empty JSON array or an object with an `ops` array")
    if any(not isinstance(item, dict) for item in payload):
        raise ValueError("every batch operation must be a JSON object")
    return payload


def _operation(args: argparse.Namespace) -> dict[str, Any] | None:
    action = args.action
    if action == "set":
        if "." not in args.target_field:
            raise ValueError("set target must use <target>.<field>, for example ksampler.steps")
        target, field = args.target_field.rsplit(".", 1)
        if not target or not field:
            raise ValueError("set target must use <target>.<field>")
        if args.value_file and args.value is not None:
            raise ValueError("choose a positional value or --value-file, not both")
        if args.value_file:
            value = Path(args.value_file).expanduser().read_text(encoding="utf-8")
        elif args.value is not None:
            value = _json_value(args.value)
        else:
            raise ValueError("set requires a value or --value-file PATH")
        return {"tool": "edit_node", "args": {
            "target": target, "field": field, "value": value,
            **({"scope_path": args.scope_path} if args.scope_path else {}),
        }}
    if action == "add":
        values: dict[str, Any] = {"class_type": args.class_type}
        if args.uid is not None:
            values["uid"] = args.uid
        if args.node_id is not None:
            values["node_id"] = args.node_id
        if args.fields is not None:
            values["fields"] = args.fields
        if args.inputs is not None:
            values["inputs"] = args.inputs
        if args.scope_path:
            values["scope_path"] = args.scope_path
        return {"tool": "add_node", "args": values}
    if action == "remove":
        return {"tool": "remove_node", "args": {"target": args.target, **({"scope_path": args.scope_path} if args.scope_path else {})}}
    if action == "connect":
        return {"tool": "upsert_link", "args": {
            "source": args.source, "target": args.target, "target_input": args.target_input,
            "source_output": _json_value(args.source_output),
            **({"scope_path": args.scope_path} if args.scope_path else {}),
        }}
    if action == "disconnect":
        return {"tool": "remove_link", "args": {
            "target": args.target, "target_input": args.target_input,
            **({"scope_path": args.scope_path} if args.scope_path else {}),
        }}
    if action == "mode":
        return {"tool": "set_node_mode", "args": {
            "target": args.target, "mode": args.mode,
            **({"scope_path": args.scope_path} if args.scope_path else {}),
        }}
    return None


def _load_json_file(path_value: str, *, label: str) -> Any:
    try:
        value = json.loads(Path(path_value).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {label} JSON: {exc}") from exc
    return value


def _exec_ports(args: argparse.Namespace) -> dict[str, Any]:
    if not args.ports:
        raise ValueError("exec add/update requires --ports PORTS.json")
    value = _load_json_file(args.ports, label="ports")
    if not isinstance(value, Mapping):
        raise ValueError("ports must be a JSON object")
    inputs = value.get("inputs", {})
    outputs = value.get("outputs", {})
    if not isinstance(inputs, Mapping) or not isinstance(outputs, Mapping):
        raise ValueError("ports.inputs and ports.outputs must be JSON objects")
    return {
        "inputs": {str(name): str(type_name) for name, type_name in inputs.items()},
        "outputs": {str(name): str(type_name) for name, type_name in outputs.items()},
    }


def _exec_source_payload(args: argparse.Namespace) -> tuple[str, dict[str, Any], str]:
    """Build source/IO fields without importing a source module."""
    from vibecomfy.runtime.python_source import capture_source, installed_entrypoint

    io = _exec_ports(args)
    if args.installed_entrypoint:
        reference = installed_entrypoint(args.installed_entrypoint, revision=args.revision)
        payload: Any = reference.to_payload()
        mode = "installed"
    elif args.project_root or args.file:
        root = args.project_root or args.file
        entrypoint = args.entrypoint
        if args.file and args.function:
            entrypoint = f"{Path(args.file).stem}:{args.function}"
        if not entrypoint:
            raise ValueError("a source file/project requires --function or --entrypoint")
        capsule = capture_source(root, entrypoint=entrypoint)
        payload = capsule.to_payload()
        mode = "snapshot"
    elif args.source_body is not None:
        return args.source_body, io, "inline"
    else:
        raise ValueError("exec add/update requires --file, --project-root, --installed-entrypoint, or --source-body")
    result_mode = args.result_mode or "mapping"
    payload["result"] = {"mode": result_mode, "outputs": io["outputs"]}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), io, mode


def _exec_bindings(args: argparse.Namespace, io: Mapping[str, Any]) -> dict[str, Any]:
    if not args.bindings:
        return {}
    value = _load_json_file(args.bindings, label="bindings")
    if not isinstance(value, Mapping):
        raise ValueError("bindings must be a JSON object")
    names = list((io.get("inputs") or {}).keys())
    return {f"in_{index}": value[name] for index, name in enumerate(names) if name in value}


def _exec_tool_call(args: argparse.Namespace) -> dict[str, Any]:
    if args.exec_action == "add":
        source, io, _mode = _exec_source_payload(args)
        uid = args.uid or "exec-" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
        bindings = _exec_bindings(args, io)
        fields: dict[str, Any] = {"source": source, "io": io}
        links: dict[str, Any] = {}
        for name, value in bindings.items():
            if (
                isinstance(value, str)
                or isinstance(value, (list, tuple))
                or (isinstance(value, Mapping) and "source" in value)
            ):
                links[name] = value
            elif isinstance(value, Mapping) and set(value) == {"literal"}:
                fields[name] = value["literal"]
            else:
                fields[name] = value
        return {
            "tool": "add_node",
            "args": {
                "class_type": "vibecomfy.exec",
                "fields": fields,
                "inputs": links,
                "uid": uid,
            },
        }
    if args.exec_action == "update":
        source, io, _mode = _exec_source_payload(args)
        operations = [
            {"op": "edit_node", "target": args.target, "field": "source", "value": source},
            {"op": "edit_node", "target": args.target, "field": "io", "value": io},
        ]
        return {"tool": "edit_batch", "args": {"ops": operations}}
    raise ValueError(f"unsupported exec edit action {args.exec_action!r}")


def _exec_inspect(args: argparse.Namespace) -> int:
    from vibecomfy.cli_loader import load_bundle
    from vibecomfy.porting.custom_python_service import inspect_exec_source_node
    from vibecomfy.schema import get_authoring_schema_provider
    from vibecomfy.ingest.snapshot import snapshot_of
    from vibecomfy.porting.edit.session import EditSession

    provider = get_authoring_schema_provider(on_demand_schemas=False)
    bundle = load_bundle(args.workflow, schema_provider=provider)
    session = EditSession(
        bundle.materialize_ui(schema_provider=provider, strict=True),
        initial_workflow=bundle.workflow,
        workflow_snapshot=snapshot_of(bundle.workflow),
        schema_provider=provider,
    )
    inspected = inspect_exec_source_node(session, args.target)
    payload = {
        "status": "ok",
        "target": args.target,
        "uid": inspected.descriptor.uid,
        "source_digest": inspected.metadata.source_digest,
        "mode": inspected.metadata.mode,
        "entrypoint": inspected.metadata.entrypoint,
        "io": {
            "inputs": [[name, type_name] for name, type_name in inspected.metadata.io["inputs"]],
            "outputs": [[name, type_name] for name, type_name in inspected.metadata.io["outputs"]],
        },
        "source": inspected.metadata.source,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{payload['mode']} exec node {payload['target']} ({payload['uid']})")
        print(f"  source digest: {payload['source_digest']}")
        if payload["entrypoint"]:
            print(f"  entrypoint: {payload['entrypoint']}")
        print(f"  inputs: {', '.join(name for name, _ in payload['io']['inputs']) or '(none)'}")
        print(f"  outputs: {', '.join(name for name, _ in payload['io']['outputs']) or '(none)'}")
    return 0


def _exec_export(args: argparse.Namespace) -> int:
    from vibecomfy.cli_loader import load_bundle
    from vibecomfy.porting.custom_python_service import inspect_exec_source_node
    from vibecomfy.schema import get_authoring_schema_provider
    from vibecomfy.ingest.snapshot import snapshot_of
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.runtime.python_source import SourceCapsule

    provider = get_authoring_schema_provider(on_demand_schemas=False)
    bundle = load_bundle(args.workflow, schema_provider=provider)
    session = EditSession(
        bundle.materialize_ui(schema_provider=provider, strict=True),
        initial_workflow=bundle.workflow,
        workflow_snapshot=snapshot_of(bundle.workflow),
        schema_provider=provider,
    )
    inspected = inspect_exec_source_node(session, args.target)
    destination = Path(args.destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    try:
        source_payload = json.loads(inspected.metadata.source)
    except (TypeError, ValueError):
        source_payload = None
    if isinstance(source_payload, Mapping) and source_payload.get("format") == "vibecomfy.python_capsule/v1":
        capsule = SourceCapsule.from_payload(source_payload)
        for member in capsule.members:
            target = destination / member.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(member.content)
    else:
        (destination / "source.py").write_text(inspected.metadata.source, encoding="utf-8")
    (destination / "manifest.json").write_text(
        json.dumps({"entrypoint": inspected.metadata.entrypoint, "io": inspected.metadata.io}, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps({"status": "saved", "destination": str(destination)}, sort_keys=True))
    else:
        print(f"Exported exec source to {destination}")
    return 0


def _targets(path: str, *, json_output: bool) -> int:
    from vibecomfy.cli_loader import load_bundle
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.schema import get_authoring_schema_provider
    from vibecomfy.ingest.snapshot import snapshot_of

    try:
        provider = get_authoring_schema_provider(on_demand_schemas=False)
        bundle = load_bundle(path, schema_provider=provider)
        bundle.require_canonical_authority("workflow target discovery")
        graph = bundle.materialize_ui(schema_provider=provider, strict=True)
        session = EditSession(
            graph,
            initial_workflow=bundle.workflow,
            workflow_snapshot=snapshot_of(bundle.workflow),
            schema_provider=provider,
        )
        targets = []
        for name, uid in sorted(session.uid_by_name.items(), key=lambda item: (item[0].casefold(), item[0])):
            node = next((node for node in bundle.workflow.nodes.values() if str(node.uid) == str(uid)), None)
            if node is None:
                continue
            targets.append({
                "target": name,
                "uid": str(uid),
                "node_id": str(node.id),
                "class_type": str(node.class_type),
                "fields": sorted(str(field) for field in node.inputs),
            })
        payload = {"status": "ok", "workflow_id": bundle.workflow.id, "revision": bundle.revision_id, "targets": targets}
    except Exception as exc:
        payload = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
        if json_output:
            print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        else:
            print(f"Could not inspect workflow targets: {payload['message']}", file=sys.stderr)
        return 1

    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"Workflow: {payload['workflow_id']} (revision {payload['revision']})")
        if not targets:
            print("(no editable node targets)")
        for item in targets:
            print(f"{item['target']}  uid={item['uid']}  node={item['node_id']}  {item['class_type']}")
            if item["fields"]:
                print(f"  fields: {', '.join(item['fields'])}")
    return 0


def _workflow_paths(reference: str | Path) -> tuple[Path, Path, Path]:
    python_path = Path(reference).expanduser()
    if python_path.is_dir() or (python_path.suffix.lower() != ".py"):
        python_path = python_path / "workflow.py"
    python_path = python_path.resolve()
    return python_path, python_path.with_suffix(".vibe.json"), python_path.parent / "source.json"


def _read_members(
    reference: str | Path,
    *,
    require_source: bool = False,
) -> tuple[Path, dict[str, bytes], dict[str, str]]:
    python_path, companion_path, source_path = _workflow_paths(reference)
    paths = {
        "workflow.py": python_path,
        "workflow.vibe.json": companion_path,
        "source.json": source_path,
    }
    try:
        members = {
            name: path.read_bytes()
            for name, path in paths.items()
            if name != "source.json" or path.exists() or require_source
        }
        if require_source and set(members) != set(paths):
            raise FileNotFoundError(paths["source.json"])
    except OSError as exc:
        raise ValueError(f"tracked workflow needs sibling workflow.py, workflow.vibe.json, and source.json members: {exc}") from exc
    digests = {name: hashlib.sha256(payload).hexdigest() for name, payload in members.items()}
    return python_path, members, digests


def _confirm_python_execution(
    *,
    args: argparse.Namespace,
    workflow_id: str,
    transition_kind: str,
    python_path: Path,
    python_digest: str,
    direct_capture: bool,
    request_digest: str | None,
) -> str:
    """Require explicit local approval before Astrid can execute workflow Python."""
    from vibecomfy.security import current_gate_context, require_confirmation

    require_confirmation(
        operation="astrid_workflow_python_execution",
        class_type="VibeWorkflow",
        provenance="untrusted_source",
        capabilities={"code_exec"},
        details={
            "workflow_id": workflow_id,
            "project": args.project,
            "transition_kind": transition_kind,
            "candidate": "direct_python_capture" if direct_capture else "tracked_workflow_edit",
            "python_path": str(python_path),
            "python_digest": python_digest,
            "request_digest": request_digest,
        },
        ctx=current_gate_context(),
    )
    # This exact scalar is an Astrid task input and is copied into its immutable
    # workflow-transition report. It is only returned after require_confirmation
    # allowed this operation through --yes or an interactive approval.
    return "confirmed"


def _tracked_edit(args: argparse.Namespace) -> dict[str, Any]:
    """Admit one canonical typed edit/capture, then materialize settled bytes."""
    from vibecomfy.commands._astrid_workflows import (
        AstridWorkflowError,
        create_task,
        digest_bytes,
        download_outputs,
        find_receipt,
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

    client = open_client()
    project_id = resolve_project(client, args.project)
    python_path, current_members, current_hashes = _read_members(args.workflow, require_source=True)
    current_as_astrid = {name: "sha256:" + digest for name, digest in current_hashes.items()}
    direct_capture = args.action == "capture" and args.ui is None

    from vibecomfy.commands._astrid_workflows import _data

    parent_receipt = find_receipt(
        project_id=project_id,
        workflow_id=None,
        member_digests=current_as_astrid,
        allow_python_mismatch=direct_capture,
    )
    if parent_receipt is None:
        raise AstridWorkflowError(
            "this exact bundle has no matching Astrid origin or accepted transition. "
            "Start its tracked history with `vibecomfy import SOURCE --project PROJECT`."
        )
    workflow_id = str(parent_receipt.get("workflow_id") or "")
    if not workflow_id:
        raise AstridWorkflowError("the local Astrid recovery receipt has no workflow identity")
    parent_task_id = str(parent_receipt.get("task_id") or "")
    parent_revision = parent_receipt.get("revision_id")
    if not parent_task_id or not isinstance(parent_revision, str) or not parent_revision:
        raise AstridWorkflowError("the local Astrid receipt is missing its parent task or revision")
    parent_origin_task = parent_receipt.get("origin_task_id")
    if parent_receipt.get("transition_kind") == "origin":
        origin_task_id = parent_task_id
    else:
        origin_task_id = str(parent_origin_task or "") or None
    if not origin_task_id:
        raise AstridWorkflowError("the tracked parent receipt has no origin task identity")

    transition_kind = "manual_capture" if args.action == "capture" else "typed_edit"
    capture_graph_bytes: bytes | None = None
    if args.action == "batch":
        ops = _load_batch(args.operations)
    elif args.action == "capture":
        ops = []
        if args.ui is not None:
            capture_graph_bytes = Path(args.ui).expanduser().read_bytes()
            graph_value = json.loads(capture_graph_bytes.decode("utf-8"))
            if not isinstance(graph_value, dict):
                raise ValueError("UI capture source must be a JSON object")
    else:
        call = _operation(args)
        if call is None:
            raise ValueError(f"unsupported tracked edit action {args.action}")
        ops = [{"op": call["tool"], **call["args"]}]
    request_digest = (
        digest_bytes(json.dumps(ops, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        if transition_kind == "typed_edit"
        else digest_bytes(capture_graph_bytes) if capture_graph_bytes is not None else None
    )
    python_execution_consent = _confirm_python_execution(
        args=args,
        workflow_id=workflow_id,
        transition_kind=transition_kind,
        python_path=python_path,
        python_digest=digest_bytes(current_members["workflow.py"]),
        direct_capture=direct_capture,
        request_digest=request_digest,
    )
    input_members = dict(current_members)
    local_precondition = dict(current_hashes)
    if direct_capture:
        # The local Python is the candidate, not the parent. Recover the exact
        # accepted parent members from the previous immutable task outputs.
        parent_task = _data(client.tasks.show(parent_task_id), action=f"read parent task {parent_task_id}")
        _old_task, parent_outputs, parent_manifest = download_outputs(
            client,
            parent_task,
            expected_names={"python", "companion", "source", "report"},
        )
        expected_parent_outputs = parent_receipt.get("outputs")
        if not isinstance(expected_parent_outputs, Mapping):
            raise AstridWorkflowError("the parent task receipt is missing settled output digests")
        for output_name, member_name in (
            ("python", "workflow.py"),
            ("companion", "workflow.vibe.json"),
            ("source", "source.json"),
        ):
            if parent_manifest.get(output_name) != expected_parent_outputs.get(member_name):
                raise AstridWorkflowError("parent task outputs no longer match the local receipt; refuse capture")
        if parent_outputs["companion"] != current_members["workflow.vibe.json"] or parent_outputs["source"] != current_members["source.json"]:
            raise AstridWorkflowError("capture candidate companion/source no longer match the accepted parent")
        input_members = {
            "workflow.py": parent_outputs["python"],
            "workflow.vibe.json": parent_outputs["companion"],
            "source.json": parent_outputs["source"],
        }
    else:
        from vibecomfy.cli_loader import load_bundle
        from vibecomfy.schema import get_authoring_schema_provider

        bundle = load_bundle(python_path, schema_provider=get_authoring_schema_provider(on_demand_schemas=False))
        bundle.require_canonical_authority("tracked workflow editing")
        if bundle.workflow.id != workflow_id or bundle.revision_id != parent_revision:
            raise AstridWorkflowError("local workflow identity/revision differs from its last Astrid receipt")
        for key, name in (
            ("workflow.py", "workflow.py"),
            ("workflow.vibe.json", "companion"),
            ("source.json", "source"),
        ):
            if parent_receipt["outputs"].get(key) != digest_bytes(current_members[key]):
                raise AstridWorkflowError("local workflow bytes differ from its last settled Astrid task")

    uploads: list[dict[str, str]] = []
    upload_payloads: list[tuple[str, str, bytes]] = [
        ("python", "workflow.py", input_members["workflow.py"]),
        ("companion", "workflow.vibe.json", input_members["workflow.vibe.json"]),
        ("source", "source.json", input_members["source.json"]),
    ]
    extra_inputs: dict[str, Any] = {
        "parent_revision": parent_revision,
        "parent_task_id": parent_task_id,
        "origin_task_id": origin_task_id,
        "transition_kind": transition_kind,
        "python_execution_consent": python_execution_consent,
    }
    operation_envelope: dict[str, Any] | None = None
    if transition_kind == "typed_edit":
        operation_envelope = {"schema_version": 1, "expected_revision": 0, "ops": ops}
        operation_bytes = (json.dumps(operation_envelope, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        upload_payloads.append(("operations", "operations.json", operation_bytes))
    elif direct_capture:
        upload_payloads.append(("capture_python", "capture_python.py", current_members["workflow.py"]))
    else:
        assert capture_graph_bytes is not None
        upload_payloads.append(("capture_graph", "capture_graph.json", capture_graph_bytes))

    request_digests: dict[str, str] = {}
    for input_name, filename, payload in upload_payloads:
        digest = digest_bytes(payload)
        request_digests[input_name] = digest
        uploads.append(upload_bytes(
            client,
            project_id,
            input_name,
            payload,
            filename=filename,
            key=stable_idempotency_key("vibecomfy-media-", {
                "project_id": project_id,
                "name": input_name,
                "digest": digest,
            }),
        ))

    task_request = {
        "project_id": project_id,
        "workflow_id": workflow_id,
        "transition_kind": transition_kind,
        "parent_revision": parent_revision,
        "parent_task_id": parent_task_id,
        "origin_task_id": origin_task_id,
        "input_digests": request_digests,
        "operations": operation_envelope,
        "python_execution_consent": python_execution_consent,
    }
    idempotency_key = stable_idempotency_key("vibecomfy-edit-", task_request)
    target = Path(args.out).expanduser().resolve() if args.out else Path(args.workflow).expanduser().resolve()
    task_id = create_task(
        client,
        project_id=project_id,
        capability="vibecomfy.edit",
        workflow_id=workflow_id,
        transition_kind=transition_kind,
        uploads=uploads,
        idempotency_key=idempotency_key,
        parent_revision=parent_revision,
        parent_task_id=parent_task_id,
        origin_task_id=origin_task_id,
        extra_inputs={key: value for key, value in extra_inputs.items() if key not in {"parent_revision", "parent_task_id", "origin_task_id", "transition_kind"}},
    )
    with track_admitted_task(task_id, target) as progress:
        receipt = {
            "schema_version": 1,
            "task_id": task_id,
            "project_id": project_id,
            "project": args.project,
            "workflow_id": workflow_id,
            "transition_kind": transition_kind,
            "idempotency_key": idempotency_key,
            "target_path": str(target),
            "separate_output": bool(args.out),
            "parent_task_id": parent_task_id,
            "origin_task_id": origin_task_id,
            "parent_revision": parent_revision,
            "python_execution_consent": python_execution_consent,
            "parent_members": {name: digest_bytes(payload) for name, payload in input_members.items()},
            "materialize_precondition": local_precondition if not args.out else None,
            "outputs": {},
            "report_digest": None,
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
        _finished_id, outputs, manifest = download_outputs(
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
        if outputs["source"] != input_members["source.json"]:
            raise AstridWorkflowError("edit task changed immutable source.json bytes")
        progress.stage = "report_validation"
        report = report_for_outputs(
            outputs,
            manifest,
            workflow_id=workflow_id,
            transition_kind=transition_kind,
            parent_revision=parent_revision,
            parent_task_id=parent_task_id,
            origin_task_id=origin_task_id,
        )
        if report.get("python_execution_consent") != python_execution_consent:
            raise AstridWorkflowError("settled report does not record the admitted Python execution consent")
        if not isinstance(report.get("security_gate_audit"), list):
            raise AstridWorkflowError("settled report is missing its Python security gate audit")
        receipt["outputs"] = dict(progress.output_digests)
        receipt["report_digest"] = manifest["report"]
        receipt["revision_id"] = report.get("revision_id")
        progress.stage = "settled_receipt"
        save_receipt(receipt)
        expected_local = None
        if not args.out:
            precondition = receipt.get("materialize_precondition")
            expected_local = {
                name: (value.removeprefix("sha256:") if isinstance(value, str) else value)
                for name, value in precondition.items()
            } if isinstance(precondition, Mapping) else None
        progress.stage = "local_publication"
        progress.local_publication = "in_progress"
        destination = materialize_outputs(outputs, target, expected_members=expected_local)
        progress.local_publication = "published"
        receipt["target_path"] = str(destination)
        progress.stage = "final_receipt"
        save_receipt(receipt)
    return {
        **report,
        "status": "saved",
        "tracking": {"mode": "astrid", "astrid": True, "project_id": project_id},
        "task_id": task_id,
        "report_digest": manifest["report"],
        "python": str(destination / "workflow.py"),
        "companion": str(destination / "workflow.vibe.json"),
        "source": str(destination / "source.json"),
        "report": report,
        "next": {
            "validate": f"vibecomfy validate {destination}",
            "history": f"astrid tasks show {task_id}; astrid tasks events {task_id}",
            "recover": f"vibecomfy recover {task_id}",
        },
    }


def _cmd_edit(args: argparse.Namespace) -> int:
    if args.action == "targets":
        return _targets(args.workflow, json_output=args.json)
    if args.action == "exec" and args.exec_action == "inspect":
        return _exec_inspect(args)
    if args.action == "exec" and args.exec_action == "export":
        return _exec_export(args)

    try:
        result = None
        if args.project and not args.dry_run:
            payload = _tracked_edit(args)
        else:
            tool_calls: list[dict[str, Any]] = []
            capture_graph = None
            capture = args.action == "capture"
            if args.action == "batch":
                tool_calls = [{"tool": "edit_batch", "args": {"ops": _load_batch(args.operations)}}]
            elif args.action == "capture" and args.ui is not None:
                capture = False
                capture_graph = json.loads(Path(args.ui).expanduser().read_text(encoding="utf-8"))
                if not isinstance(capture_graph, dict):
                    raise ValueError("UI capture source must be a JSON object")
            elif args.action == "exec":
                tool_calls = [_exec_tool_call(args)]
            else:
                operation = _operation(args)
                if operation is not None:
                    tool_calls = [operation]

            from vibecomfy.porting.edit.bundle_service import transition_bundle

            input_path, _input_members, _input_hashes = _read_members(args.workflow)
            before_members = {}
            for name, path in (
                ("workflow.py", input_path),
                ("workflow.vibe.json", input_path.with_suffix(".vibe.json")),
                ("source.json", input_path.parent / "source.json"),
            ):
                try:
                    before_members[name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                except OSError:
                    pass
            result = transition_bundle(
                args.workflow,
                tool_calls=tool_calls,
                capture=capture,
                capture_graph=capture_graph,
                output=args.out,
                dry_run=args.dry_run,
            )
            payload = result.to_dict()
            payload["status"] = result.status
            payload["tracking"] = (
                {"mode": "astrid_preview", "astrid": False, "project": args.project}
                if args.project
                else {"mode": "untracked", "astrid": False}
            )
            payload["next"] = {
                "validate": f"vibecomfy validate {args.out or args.workflow}",
                "inspect": f"vibecomfy inspect {args.out or args.workflow}",
                "tracking": "preview only; omit --project to save locally, or pass --project <project> to record in Astrid",
            }
            if result.status == "saved":
                from vibecomfy.cli_loader import load_bundle

                python_path = Path(result.python_path)
                after_members = {}
                for name, path in (
                    ("workflow.py", python_path),
                    ("workflow.vibe.json", python_path.with_suffix(".vibe.json")),
                    ("source.json", python_path.parent / "source.json"),
                ):
                    try:
                        after_members[name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                    except OSError:
                        pass
                bundle = load_bundle(python_path)
                before = None
                if result.parent_revision:
                    before = {
                        "revision_id": result.parent_revision,
                        "parent_revision": None,
                        "semantic_digest": result.before_semantic_digest,
                        "ui_digest": result.before_ui_digest,
                        "members": before_members,
                    }
                transition_kind = "manual_capture" if result.kind == "python_capture" else "typed_edit"
                payload["report"] = {
                    "schema_version": 1,
                    "transition_kind": transition_kind,
                    "workflow_id": bundle.workflow.id,
                    "workflow_identity": bundle.workflow_identity,
                    "revision_id": result.revision_id,
                    "parent_revision": result.parent_revision,
                    "parent_task_id": None,
                    "origin_task_id": None,
                    "before": before,
                    "after": {
                        "revision_id": result.revision_id,
                        "parent_revision": result.parent_revision,
                        "semantic_digest": result.semantic_digest,
                        "ui_digest": result.ui_digest,
                        "members": after_members,
                    },
                    "members": after_members,
                    "operations": payload.get("operations", []),
                    "diff": payload.get("diff"),
                    "diff_status": payload.get("diff_status"),
                    "diagnostics": payload.get("diagnostics", []),
                    "tracking": payload["tracking"],
                }
    except Exception as exc:
        from vibecomfy.commands._astrid_workflows import TrackedWorkflowFailure

        if isinstance(exc, TrackedWorkflowFailure):
            payload = exc.to_payload()
        else:
            payload = {
                "status": "error",
                "message": f"{type(exc).__name__}: {exc}",
                "recovery": "Inspect targets with `vibecomfy edit <workflow> targets`, check node details with `vibecomfy node <ClassType>`, and retry with a fresh workflow revision.",
            }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        else:
            print(f"Edit failed: {payload['message']}", file=sys.stderr)
            if payload.get("task_id"):
                print(f"  Astrid task: {payload['task_id']} (stage: {payload.get('stage', 'unknown')})", file=sys.stderr)
                astrid = payload.get("astrid_outputs", {})
                if isinstance(astrid, dict):
                    print(f"  Astrid outputs: {astrid.get('status', 'unknown')}", file=sys.stderr)
                    if astrid.get("report_digest"):
                        print(f"  report digest: {astrid['report_digest']}", file=sys.stderr)
                print(f"  local publication: {payload.get('local_publication', 'unknown')}", file=sys.stderr)
            print(payload["recovery"], file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        if result is None:
            print(f"Saved {payload['transition_kind']}: {payload['python']}")
            print(f"  revision: {payload['revision_id']}")
            print(f"  parent:   {payload['parent_revision']}")
            print(f"  task:     {payload['task_id']} (report {payload['report_digest']})")
            print(f"  validate: {payload['next']['validate']}")
            print(f"  history:  {payload['next']['history']}")
        else:
            status = "Preview" if result.status == "preview" else "Saved"
            print(f"{status} {result.kind}: {result.python_path}")
            print(f"  revision: {result.revision_id}")
            if result.parent_revision:
                print(f"  parent:   {result.parent_revision}")
            print(f"  tracking: {payload['tracking']['mode']}")
            print(f"  validate: vibecomfy validate {args.out or args.workflow}")
            if args.action == "capture":
                print("  capture records the aggregate workflow state; it does not invent individual edits")
                if result.parent_revision is None:
                    print("  baseline: no trusted pre-capture snapshot was available; this capture starts a new baseline")
    return 0


def _configure(subparsers, name: str, help_text: str, args_fn) -> None:
    command = subparsers.add_parser(name, help=help_text)
    args_fn(command)
    command.set_defaults(func=_cmd_edit)


def register(subparsers) -> None:
    edit = subparsers.add_parser(
        "edit",
        help="Edit, batch, or explicitly capture an imported workflow.",
        description=(
            "Apply one typed workflow operation or one atomic batch through the canonical\n"
            "bundle editor. Edits update the Python/companion pair together and preserve\n"
            "source.json. Use --dry-run to preview and --out to save a separate bundle."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    edit.add_argument("workflow", help="Workflow Python file or imported workflow folder.")
    edit.add_argument("--out", help="Write to a separate bundle directory instead of replacing the input.")
    edit.add_argument("--project", help="Opt into Astrid task tracking for accepted changes.")
    edit.add_argument("--dry-run", action="store_true", help="Validate and preview without publishing files.")
    edit.add_argument("--json", action="store_true", help="Emit a JSON result.")
    actions = edit.add_subparsers(dest="action", required=True)

    def set_args(parser):
        parser.add_argument("target_field", help="Target binding and field, such as ksampler.steps.")
        parser.add_argument("value", nargs="?", help="JSON value, or unquoted text treated as a string.")
        parser.add_argument("--value-file", help="Read the complete field value as UTF-8 text from this file.")
        parser.add_argument("--scope-path", default="")

    def add_args(parser):
        parser.add_argument("class_type")
        parser.add_argument("--uid", help="Stable identity for later references inside this batch.")
        parser.add_argument("--node-id")
        parser.add_argument("--fields", type=lambda value: _json_object(value, option="--fields"))
        parser.add_argument("--inputs", type=lambda value: _json_object(value, option="--inputs"))
        parser.add_argument("--scope-path", default="")

    def remove_args(parser):
        parser.add_argument("target")
        parser.add_argument("--scope-path", default="")

    def connect_args(parser):
        parser.add_argument("source")
        parser.add_argument("target")
        parser.add_argument("target_input")
        parser.add_argument("--source-output", default="0")
        parser.add_argument("--scope-path", default="")

    def disconnect_args(parser):
        parser.add_argument("target")
        parser.add_argument("target_input")
        parser.add_argument("--scope-path", default="")

    def mode_args(parser):
        parser.add_argument("target")
        parser.add_argument("mode", choices=("enabled", "muted", "bypassed"))
        parser.add_argument("--scope-path", default="")

    _configure(actions, "set", "Set one node field.", set_args)
    _configure(actions, "add", "Add one node.", add_args)
    _configure(actions, "remove", "Remove one node.", remove_args)
    _configure(actions, "connect", "Connect a named input to a node output.", connect_args)
    _configure(actions, "disconnect", "Remove a link from a named input.", disconnect_args)
    _configure(actions, "mode", "Set a node to enabled, muted, or bypassed.", mode_args)

    batch = actions.add_parser("batch", help="Apply ordered JSON operations atomically.")
    batch.add_argument("operations", nargs="?", default="-", help="JSON file path; use - or omit it to read stdin.")
    batch.set_defaults(func=_cmd_edit)

    capture = actions.add_parser("capture", help="Capture direct Python changes or a UI graph as one revision.")
    capture.add_argument("--ui", help="Capture a ComfyUI JSON graph instead of edited Python.")
    capture.set_defaults(func=_cmd_edit)

    exec_parser = actions.add_parser(
        "exec",
        help="Add, update, inspect, or export a Python-backed vibecomfy.exec node.",
    )
    exec_parser.set_defaults(func=_cmd_edit)
    exec_actions = exec_parser.add_subparsers(dest="exec_action", required=True)

    def source_args(parser, *, update: bool = False) -> None:
        if update:
            parser.add_argument("target", help="Stable exec binding or UID.")
        parser.add_argument("--file", help="Python module file to snapshot.")
        parser.add_argument("--function", help="Entrypoint function in --file.")
        parser.add_argument("--project-root", help="Python project/package root to snapshot.")
        parser.add_argument("--entrypoint", help="Snapshot-relative module:function entrypoint.")
        parser.add_argument("--installed-entrypoint", help="Worker-installed fully qualified module:function.")
        parser.add_argument("--source-body", help="Inline exec body returning the declared output mapping.")
        parser.add_argument("--ports", required=True, help="JSON file containing inputs and outputs mappings.")
        parser.add_argument("--bindings", help="JSON object of semantic input values or existing bindings.")
        parser.add_argument("--uid", help="Stable UID for a new node.")
        parser.add_argument("--revision", help="Optional installed-package revision/cache token.")
        parser.add_argument("--result-mode", choices=("mapping", "single", "tuple", "list"), default="mapping")

    add_exec = exec_actions.add_parser("add", help="Add one source-backed exec node atomically.")
    source_args(add_exec)

    update_exec = exec_actions.add_parser("update", help="Update one exec node's source and interface atomically.")
    source_args(update_exec, update=True)

    inspect_exec = exec_actions.add_parser("inspect", help="Inspect one exec node's source, mode, and ports.")
    inspect_exec.add_argument("target")

    export_exec = exec_actions.add_parser("export", help="Export one embedded source capsule or inline body.")
    export_exec.add_argument("target")
    export_exec.add_argument("--destination", required=True)

    targets = actions.add_parser("targets", help="List edit targets, stable UIDs, classes, and fields.")
    targets.set_defaults(func=_cmd_edit)
