from __future__ import annotations

import argparse
import ast
import datetime as _dt
import difflib
import hashlib
import json
import re
import shlex
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys
from collections.abc import Mapping

from vibecomfy.analysis.corpus import build_corpus_snapshot
from vibecomfy.analysis.node_coverage import build_workflow_coverage
from vibecomfy.commands._diagnostics import Diagnostic, diagnostics_to_json, diagnostics_to_text
from vibecomfy.commands._output import emit
from vibecomfy.commands._index_files import IndexReadError, print_index_error, read_index_json
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.registry import load_workflow_reference
from vibecomfy.registry.pack_resolver import PackResolverError, resolve_pack
from vibecomfy.schema import (
    SchemaIndexError,
    SchemaProviderError,
    get_authoring_schema_provider,
    get_schema_provider,
    schemas_for,
    socket_types_compatible,
)
import vibecomfy.node_packs as node_packs_install
from vibecomfy.node_packs import LockEntry, read_lockfile, write_lockfile
from vibecomfy.porting.wrappers import codegen as _wrapper_codegen
from vibecomfy.porting.wrappers import discovery as _wrapper_discovery


from vibecomfy.ingest.normalize import door_get_links, door_get_nodes
def _cmd_nodes_list(args: argparse.Namespace) -> int:
    path = Path("node_index.json")
    if not path.exists():
        print("node_index.json not found; run `vibecomfy sources sync`")
        return 1
    try:
        rows = read_index_json(path, default=[])
    except IndexReadError as exc:
        print_index_error(exc)
        return 1
    return emit(rows[: args.limit], json=args.json, text_renderer=lambda selected: "\n".join(str(row) for row in selected))


def _cmd_nodes_spec(args: argparse.Namespace) -> int:
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", args.class_type, re.I):
        return _cmd_nodes_spec_subgraph(args)
    provider = get_authoring_schema_provider(object_info_cache_path=args.object_info_cache)
    try:
        schema = provider.get_schema(args.class_type)
    except SchemaIndexError as exc:
        print(f"{exc}; run `vibecomfy sources sync` to rebuild indexes.")
        return 1
    if schema is None:
        print(
            f"node schema not found for {args.class_type!r}; run `vibecomfy sources sync`, "
            "start a runtime with /object_info, or install the custom node source locally"
        )
        return 1
    print(json.dumps(asdict(schema), indent=2, sort_keys=True))
    return 0


def _cmd_nodes_compatible_with(args: argparse.Namespace) -> int:
    provider = get_authoring_schema_provider(object_info_cache_path=getattr(args, "object_info_cache", None))
    if getattr(args, "to_class", None) is None:
        payload = _compatible_socket_search(provider, args.type_or_from_class, socket_role=args.socket_role)
        if getattr(args, "json", False):
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"compatible {args.socket_role} sockets for {args.type_or_from_class}: {payload['compatible_count']}")
            for match in payload["matches"][:25]:
                print(f"- {match['class_type']}.{match['socket']} ({match['socket_type']})")
        return 0
    if getattr(args, "to_input", None) is None:
        print("to_input is required when checking a concrete node endpoint", file=sys.stderr)
        return 2
    from_schema = provider.get_schema(args.type_or_from_class)
    to_schema = provider.get_schema(args.to_class)
    from_output = str(getattr(args, "from_output", "0"))
    to_input = str(args.to_input)
    output_type = _schema_output_type(from_schema, from_output)
    input_type = _schema_input_type(to_schema, to_input)
    compatible = socket_types_compatible(output_type, input_type)
    payload = {
        "from_class": args.type_or_from_class,
        "from_output": from_output,
        "from_output_type": output_type,
        "to_class": args.to_class,
        "to_input": to_input,
        "to_input_type": input_type,
        "compatible": compatible,
        "known": output_type is not None and input_type is not None,
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        verdict = "compatible" if compatible else "incompatible"
        print(f"{args.type_or_from_class}.{from_output} -> {args.to_class}.{to_input}: {verdict}")
        print(f"output_type={output_type or 'unknown'} input_type={input_type or 'unknown'}")
    return 0 if compatible else 1


def _schema_output_type(schema: object | None, output: str) -> str | None:
    outputs = getattr(schema, "outputs", None) or []
    try:
        index = int(output)
    except (TypeError, ValueError):
        index = None
    if index is not None and 0 <= index < len(outputs):
        value = getattr(outputs[index], "type", None)
        return str(value) if value is not None else None
    for item in outputs:
        if getattr(item, "name", None) == output:
            value = getattr(item, "type", None)
            return str(value) if value is not None else None
    return None


def _schema_input_type(schema: object | None, input_name: str) -> str | None:
    spec = (getattr(schema, "inputs", {}) or {}).get(input_name)
    value = getattr(spec, "type", None)
    return str(value) if value is not None else None


def _compatible_socket_search(provider: object, socket_type: str, *, socket_role: str) -> dict[str, object]:
    schemas = schemas_for(provider) or {}
    getter = getattr(provider, "get_schema", None) or getattr(provider, "get", None)
    matches: list[dict[str, object]] = []
    for class_type, schema in sorted(schemas.items()):
        # Object-info index providers intentionally expose a listing-only
        # ``schemas()`` surface: values are ``None`` until a consumer asks for
        # one class.  Compatible-with is a real schema consumer, so focus-load
        # each advertised class through the canonical getter.  A getter error
        # is provider failure, not an absent class, and must remain typed.
        if schema is None and callable(getter):
            try:
                schema = getter(class_type)
            except SchemaProviderError:
                raise
            except Exception as exc:
                raise SchemaProviderError(str(class_type), exc) from exc
        if schema is None:
            continue
        if socket_role == "input":
            for input_name, spec in (getattr(schema, "inputs", None) or {}).items():
                candidate_type = getattr(spec, "type", None)
                if candidate_type is not None and socket_types_compatible(socket_type, candidate_type):
                    matches.append(
                        {
                            "class_type": str(class_type),
                            "socket": str(input_name),
                            "socket_role": "input",
                            "socket_type": str(candidate_type) if candidate_type is not None else None,
                        }
                    )
        else:
            for output_index, output in enumerate(getattr(schema, "outputs", None) or []):
                candidate_type = getattr(output, "type", None)
                if candidate_type is not None and socket_types_compatible(candidate_type, socket_type):
                    matches.append(
                        {
                            "class_type": str(class_type),
                            "socket": str(getattr(output, "name", None) or output_index),
                            "socket_role": "output",
                            "socket_type": str(candidate_type) if candidate_type is not None else None,
                        }
                    )
    return {
        "type": socket_type,
        "as": socket_role,
        "classes": sorted({str(match["class_type"]) for match in matches}),
        "matches": matches,
        "compatible_count": len(matches),
        "provider": type(provider).__name__,
    }


def _cmd_nodes_spec_subgraph(args: argparse.Namespace) -> int:
    candidates: list[Path] = []
    source = getattr(args, "source", None)
    if source:
        candidates.append(Path(source))
    else:
        candidates.extend(Path("ready_templates/sources").rglob("*.json"))
    for path in candidates:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        definitions = raw.get("definitions") if isinstance(raw, dict) else None
        subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
        if isinstance(subgraphs, dict):
            iterable = subgraphs.values()
        elif isinstance(subgraphs, list):
            iterable = subgraphs
        else:
            iterable = ()
        for subgraph in iterable:
            if not isinstance(subgraph, dict) or str(subgraph.get("id")) != args.class_type:
                continue
            class_counts: dict[str, int] = {}
            for node in door_get_nodes(subgraph) or ():
                if isinstance(node, dict):
                    class_type = str(node.get("type") or node.get("class_type") or "Unknown")
                    class_counts[class_type] = class_counts.get(class_type, 0) + 1
            payload = {
                "uuid": args.class_type,
                "name": subgraph.get("name"),
                "inputs": subgraph.get("inputs") or [],
                "outputs": subgraph.get("outputs") or [],
                "inner_node_count": len(door_get_nodes(subgraph) or []),
                "inner_node_class_types": dict(sorted(class_counts.items())),
                "inner_graph": {"edges": door_get_links(subgraph) or []},
                "source": str(path),
            }
            return emit(payload, json=getattr(args, "json", False), text_renderer=lambda data: data["name"] or data["uuid"])
    print(f"subgraph UUID not found: {args.class_type}", file=sys.stderr)
    return 1


def _cmd_nodes_install_plan(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(args.path, schema_provider=schema_provider, allow_scratchpad=True)
    try:
        missing_classes = node_packs_install.missing_class_types_for_workflow(workflow)
        packs, unresolved = node_packs_install.missing_packs_for_workflow(workflow)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = build_nodes_install_plan_payload(args.path, missing_classes, packs, unresolved)
    return _print_install_plan(payload, json_output=args.json)


def build_nodes_install_plan_payload(path: str, missing_classes, packs, unresolved) -> dict[str, object]:
    return {
        "path": path,
        "packs": [
            {
                "name": pack.name,
                "repo": pack.repo,
                "pip_packages": list(pack.pip_packages),
                "classes": sorted(missing_classes & pack.classes),
            }
            for pack in packs
        ],
        "unresolved_class_types": unresolved,
        "missing_class_types": sorted(missing_classes),
    }


_RECONCILE_SCHEMA_VERSION = "vibecomfy.nodes.reconcile.v1"


def _reconcile_quote(value: object) -> str:
    """Quote every interpolated token, including tokens safe without quotes."""
    text = str(value)
    quoted = shlex.quote(text)
    return quoted if quoted != text else f"'{text}'"


def _reconcile_jsonable(value: object) -> object:
    """Convert report details to a stable JSON-compatible tree."""
    if isinstance(value, Mapping):
        return {str(key): _reconcile_jsonable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_reconcile_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_reconcile_jsonable(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _reconcile_diagnostic(
    subject_type: str,
    code: str,
    message: str,
    *,
    target: str,
    severity: str = "error",
    recoverable: bool = True,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    detail = dict(details or {})
    detail.setdefault("target", target)
    return {
        "subject_type": subject_type,
        "code": code,
        "message": message,
        "severity": severity,
        "recoverable": recoverable,
        "details": _reconcile_jsonable(detail),
    }


def _reconcile_command(args: argparse.Namespace) -> str:
    parts = ["vibecomfy", "nodes", "reconcile", "--workflow", _reconcile_quote(args.workflow), "--json"]
    for name in ("lockfile", "registry", "models_root"):
        value = getattr(args, name, None)
        if value:
            parts.extend([f"--{name.replace('_', '-')}", _reconcile_quote(value)])
    if getattr(args, "server_url", None):
        parts.extend(["--server-url", _reconcile_quote(args.server_url)])
    return " ".join(parts)


def _reconcile_wrapper_class_map(module_path: Path) -> dict[str, str]:
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    except (OSError, SyntaxError):
        return {}
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if not any(isinstance(target, ast.Name) and target.id == "__vibecomfy_class_types__" for target in targets):
            continue
        try:
            value = ast.literal_eval(statement.value)
        except (ValueError, TypeError):
            return {}
        return {str(key): str(item) for key, item in value.items()} if isinstance(value, dict) else {}
    return {}


def _reconcile_refresh_remediation(
    *, class_type: str, source: Mapping[str, object] | None, workflow_command: str
) -> tuple[str, str]:
    source_path = None
    if source:
        for key in ("capture_path", "source_path", "path", "cache_path"):
            candidate = source.get(key)
            if isinstance(candidate, str) and candidate and Path(candidate).is_file():
                source_path = candidate
                break
    if source_path is not None:
        command = f"vibecomfy schemas refresh --source {_reconcile_quote(source_path)} --json"
    else:
        command = f"provide a local object-info dump for {_reconcile_quote(class_type)} and rerun {_reconcile_quote(workflow_command)}"
    return "refresh", command


def _reconcile_model_references(workflow: object) -> list[dict[str, str]]:
    """Collect model references without invoking runtime preflight."""
    from vibecomfy.model_assets import _referenced_model_values

    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for reference in _referenced_model_values(workflow):
        value = str(reference.get("value", ""))
        subdir = str(reference.get("subdir", ""))
        key = (value, subdir)
        if value and key not in seen:
            refs.append({"value": value, "subdir": subdir})
            seen.add(key)
    metadata = getattr(workflow, "metadata", {})
    for entry in metadata.get("model_assets", []) if isinstance(metadata, Mapping) else []:
        if not isinstance(entry, Mapping):
            continue
        value = entry.get("name")
        subdir = entry.get("subdir", entry.get("directory", ""))
        if isinstance(value, str) and value:
            key = (value, str(subdir))
            if key not in seen:
                refs.append({"value": value, "subdir": str(subdir)})
                seen.add(key)
    requirements = getattr(workflow, "requirements", None)
    for value in getattr(requirements, "models", ()) if requirements is not None else ():
        if not isinstance(value, str) or not value:
            continue
        key = (value, "")
        if key not in seen:
            refs.append({"value": value, "subdir": ""})
            seen.add(key)
    return sorted(refs, key=lambda item: (item["value"], item["subdir"]))


def build_nodes_reconcile_payload(args: argparse.Namespace) -> dict[str, object]:
    """Build the deterministic report without invoking mutation or runtime code."""
    lock_path = Path(getattr(args, "lockfile", None) or "custom_nodes.lock")
    # Parse before provider/discovery work: malformed locks must remain observable.
    lock_entries = read_lockfile(lock_path)
    known_packs = node_packs_install.get_known_node_packs(lock_path)
    pack_by_class: dict[str, object] = {}
    for pack in known_packs:
        for class_type in pack.classes:
            pack_by_class.setdefault(str(class_type), pack)
    pack_by_name = {str(pack.name): pack for pack in known_packs}
    pack_slug_by_name = {
        str(entry.name): str(entry.slug or entry.name) for entry in lock_entries
    }
    lock_entry_by_name = {str(entry.name): entry for entry in lock_entries}

    provider = get_authoring_schema_provider(on_demand_schemas=False)
    workflow = load_workflow_reference(
        str(args.workflow), schema_provider=provider, allow_scratchpad=True
    )
    diagnostics: list[dict[str, object]] = []
    remediations: list[dict[str, object]] = []
    node_classes = {str(node.class_type) for node in workflow.nodes.values()}
    try:
        schema_classes = set(provider.schemas())
    except Exception:
        schema_classes = set()
    missing_classes = set(node_classes) - schema_classes - set(node_packs_install.CORE_COMFY_CLASSES)
    # Preserve the existing requirements boundary and the canonical helper for
    # the default lock while avoiding its ambient lock path for explicit locks.
    if lock_path == Path("custom_nodes.lock"):
        missing_classes.update(node_packs_install.missing_class_types_for_workflow(workflow))
    missing_classes.update(str(item) for item in getattr(workflow.requirements, "missing_nodes", ()))
    if missing_classes:
        for class_type in sorted(missing_classes):
            pack = pack_by_class.get(class_type)
            if pack is not None:
                slug = pack_slug_by_name.get(pack.name, pack.name)
                diagnostics.append(
                    _reconcile_diagnostic(
                        "node", "missing_node_pack", f"node pack {slug!r} is required for {class_type!r}",
                        target=class_type, details={"class_type": class_type, "pack": slug},
                    )
                )
                remediations.append({"action": "install", "command": f"vibecomfy nodes install {_reconcile_quote(slug)}", "targets": [slug]})
            else:
                diagnostics.append(
                    _reconcile_diagnostic(
                        "node", "unknown_node", f"node class {class_type!r} is not resolved locally",
                        target=class_type, details={"class_type": class_type},
                    )
                )
                remediations.append({"action": "lookup", "command": f"vibecomfy nodes lookup {_reconcile_quote(class_type)} --json", "targets": [class_type]})

    # Declared packs are independently actionable even when their class set is empty.
    for declared in sorted(set(str(item) for item in getattr(workflow.requirements, "custom_nodes", ()) )):
        if declared in pack_by_name:
            continue
        diagnostics.append(_reconcile_diagnostic("node", "missing_node_pack", f"declared node pack {declared!r} is not installed", target=declared, details={"pack": declared}))
        remediations.append({"action": "install", "command": f"vibecomfy nodes install {_reconcile_quote(declared)}", "targets": [declared]})

    # Compare generated public maps locally. Generation and registration are only
    # remediation strings; no module is imported or regenerated here.
    modules_file = Path(__file__).resolve().parents[1] / "nodes" / "__init__.py"
    module_names: set[str] = set()
    try:
        module_tree = ast.parse(modules_file.read_text(encoding="utf-8"), filename=str(modules_file))
        for statement in module_tree.body:
            if isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "MODULES" for target in statement.targets):
                values = ast.literal_eval(statement.value)
                module_names = {str(item) for item in values} if isinstance(values, list) else set()
    except (OSError, SyntaxError, ValueError, TypeError):
        module_names = set()
    checked_packs: set[str] = set()
    for class_type in sorted(node_classes & set(pack_by_class)):
        pack = pack_by_class[class_type]
        pack_name = str(pack.name)
        if pack_name in checked_packs:
            continue
        checked_packs.add(pack_name)
        slug = pack_slug_by_name.get(pack_name, pack_name)
        module_stem = _wrapper_codegen._slug_to_module_name(slug)
        module_path = modules_file.parent / f"{module_stem}.py"
        wrapper_map = _reconcile_wrapper_class_map(module_path) if module_path.is_file() else {}
        if not module_path.is_file() or class_type not in wrapper_map:
            diagnostics.append(_reconcile_diagnostic("node", "wrapper_drift", f"generated wrapper for {class_type!r} in {slug!r} is missing or stale", target=class_type, details={"class_type": class_type, "pack": slug, "module": module_stem}))
            command = f"vibecomfy nodes generate-wrappers {_reconcile_quote(slug)} --source cache --deterministic-timestamp"
            remediations.append({"action": "regenerate", "command": command, "targets": [slug]})
            if module_stem not in module_names:
                diagnostics.append(_reconcile_diagnostic("node", "wrapper_registration_missing", f"wrapper module {module_stem!r} is not registered in vibecomfy.nodes; generation does not update exports", target=module_stem, details={"pack": slug, "module": module_stem, "registration_command_available": False}))
                remediations.append({"action": "register", "command": f"add module stem {_reconcile_quote(module_stem)} to {_reconcile_quote(modules_file)}; generation does not update exports", "targets": [module_stem]})

    # Identity/schema mismatches are local, fail-closed diagnostics.
    for node_id, node in sorted(workflow.nodes.items(), key=lambda pair: str(pair[0])):
        class_type = str(node.class_type)
        try:
            schema = provider.get_schema(class_type)
        except Exception:
            schema = None
        pack = pack_by_class.get(class_type)
        source = node.metadata.get("schema_source") if isinstance(node.metadata, Mapping) else None
        expected_pack = str(pack.name) if pack is not None else None
        source_pack = source.get("pack") or source.get("package") if isinstance(source, Mapping) else None
        schema_pack = getattr(schema, "pack", None)
        if expected_pack and source_pack and str(source_pack) not in {expected_pack, pack_slug_by_name.get(expected_pack, expected_pack)}:
            diagnostics.append(_reconcile_diagnostic("node", "identity_mismatch", f"schema identity for {class_type!r} does not match {expected_pack!r}", target=class_type, details={"node_id": str(node_id), "class_type": class_type, "expected_pack": expected_pack, "actual_pack": str(source_pack)}))
            action, command = _reconcile_refresh_remediation(class_type=class_type, source=source if isinstance(source, Mapping) else None, workflow_command=_reconcile_command(args))
            remediations.append({"action": action, "command": command, "targets": [class_type]})
        if schema_pack and expected_pack and str(schema_pack) not in {expected_pack, pack_slug_by_name.get(expected_pack, expected_pack)}:
            diagnostics.append(_reconcile_diagnostic("node", "schema_mismatch", f"schema pack for {class_type!r} does not match {expected_pack!r}", target=class_type, details={"node_id": str(node_id), "class_type": class_type, "expected_pack": expected_pack, "actual_pack": str(schema_pack)}))
        if expected_pack:
            lock_entry = lock_entry_by_name.get(expected_pack)
            identity: dict[str, str] | None = None
            if isinstance(source, Mapping):
                source_commit = source.get("git_commit") or source.get("commit")
                source_evidence = source.get("evidence_identity")
                source_slug = source.get("pack_slug") or source.get("pack") or source.get("package")
                if source_slug and source_commit:
                    identity = {"pack_slug": str(source_slug), "git_commit": str(source_commit)}
                elif source_slug and source_evidence:
                    identity = {"pack_slug": str(source_slug), "evidence_identity": str(source_evidence)}
            if identity is None and lock_entry is not None:
                commit = lock_entry.commit or lock_entry.git_commit_sha
                if commit:
                    identity = {"pack_slug": pack_slug_by_name.get(expected_pack, expected_pack), "git_commit": str(commit)}
            if identity is not None:
                from vibecomfy.porting.object_info.consume import resolve_class_entry

                identity_result = resolve_class_entry(class_type, identity, allow_class_fallback=False)
                if identity_result.entry is None:
                    diagnostics.append(_reconcile_diagnostic("node", "identity_mismatch", f"object-info identity for {class_type!r} is not available for the locked pack", target=class_type, details={"node_id": str(node_id), "class_type": class_type, "identity": identity, "lookup_source": identity_result.source}))
                    action, command = _reconcile_refresh_remediation(class_type=class_type, source=source if isinstance(source, Mapping) else None, workflow_command=_reconcile_command(args))
                    remediations.append({"action": action, "command": command, "targets": [class_type]})
            else:
                diagnostics.append(_reconcile_diagnostic("node", "identity_unavailable", f"no committed object-info identity is available for {class_type!r}", target=class_type, severity="warning", details={"node_id": str(node_id), "class_type": class_type, "pack": expected_pack, "identity_available": False}))
        if schema is not None:
            required = sorted(name for name, spec in (getattr(schema, "inputs", {}) or {}).items() if getattr(spec, "required", False))
            present = set(node.inputs) | set(node.widgets)
            missing_required = [name for name in required if name not in present]
            if missing_required:
                diagnostics.append(_reconcile_diagnostic("node", "schema_mismatch", f"node {class_type!r} is missing required inputs", target=class_type, details={"node_id": str(node_id), "class_type": class_type, "missing_required_inputs": missing_required}))
                action, command = _reconcile_refresh_remediation(class_type=class_type, source=source if isinstance(source, Mapping) else None, workflow_command=_reconcile_command(args))
                remediations.append({"action": action, "command": command, "targets": [class_type]})

    try:
        from vibecomfy import fetch as fetch_assets
        from vibecomfy.registry import models_loader
        registry = models_loader.load_registry(getattr(args, "registry", None))
        model_refs = _reconcile_model_references(workflow)
        for reference in model_refs:
            value, subdir = reference["value"], reference["subdir"]
            entry = models_loader.resolve_model_entry(value, registry=registry, subdir=subdir or None)
            if entry is None:
                registry_path = str(getattr(args, "registry", None) or models_loader.DEFAULT_REGISTRY_PATH)
                diagnostics.append(_reconcile_diagnostic("model", "unknown_model", f"model reference {value!r} is not in the local registry", target=value, details={"value": value, "subdir": subdir, "registry_path": registry_path, "registry_lookup": False, "registration_command_available": False}))
                rerun = _reconcile_command(args)
                command = f"add a valid model row to {_reconcile_quote(registry_path)} and rerun {_reconcile_quote(rerun)}"
                remediations.append({"action": "register", "command": command, "targets": [value]})
                continue
            effective_subdir = subdir or (Path(entry.targets[0].path).parent.as_posix() if entry.targets else "")
            asset = {"name": value, "subdir": effective_subdir}
            try:
                present = fetch_assets.is_present(asset, root=Path(args.models_root) if getattr(args, "models_root", None) else None)
            except (KeyError, OSError, ValueError) as exc:
                diagnostics.append(_reconcile_diagnostic("model", "model_presence_error", f"cannot inspect model {value!r}: {type(exc).__name__}", target=value, details={"value": value, "subdir": effective_subdir, "error": str(exc)}))
                continue
            if not present:
                diagnostics.append(_reconcile_diagnostic("model", "missing_model", f"model {value!r} is registered but absent locally", target=value, details={"value": value, "model_id": entry.id, "subdir": effective_subdir}))
                command_parts = ["vibecomfy", "models", "stage", "--ids", _reconcile_quote(entry.id)]
                if getattr(args, "registry", None):
                    command_parts.extend(["--registry", _reconcile_quote(args.registry)])
                if getattr(args, "models_root", None):
                    command_parts.extend(["--models-root", _reconcile_quote(args.models_root)])
                remediations.append({"action": "stage", "command": " ".join(command_parts), "targets": [entry.id]})
    except Exception as exc:
        diagnostics.append(_reconcile_diagnostic("model", "model_registry_error", f"model registry could not be read: {type(exc).__name__}", target="registry", details={"error": str(exc)}))

    if getattr(args, "server_url", None) is not None:
        url = str(args.server_url).strip()
        if not url:
            raise ValueError("--server-url must not be empty")
        from vibecomfy.runtime.session import _nodepack_reload_status
        runtime_status = _nodepack_reload_status(url)
        if runtime_status == "restart_required":
            diagnostics.append(_reconcile_diagnostic("runtime", "restart_required", f"externally owned runtime {url!r} must be restarted", target=url, severity="warning", details={"server_url": url, "lifecycle_calls": 0}))
            remediations.append({"action": "restart-runtime", "command": f"restart the externally owned ComfyUI server at {_reconcile_quote(url)}", "targets": [url]})

    diagnostics = sorted(diagnostics, key=lambda item: (str(item["subject_type"]), str(item["code"]), str(item["details"].get("target", "")), str(item["message"])))
    for remediation in remediations:
        remediation["targets"] = sorted({str(item) for item in remediation.get("targets", [])})
    remediations = sorted(remediations, key=lambda item: (str(item["action"]), str(item["targets"][0] if item["targets"] else ""), str(item["command"])))
    blocked = any(item["severity"] == "error" for item in diagnostics)
    restart_required = any(item["code"] == "restart_required" for item in diagnostics)
    status = "blocked" if blocked else ("restart_required" if restart_required else "ok")
    return {"schema_version": _RECONCILE_SCHEMA_VERSION, "status": status, "diagnostics": diagnostics, "remediations": remediations}


def _cmd_nodes_reconcile(args: argparse.Namespace) -> int:
    if getattr(args, "server_url", None) is not None and not str(args.server_url).strip():
        print("--server-url must not be empty", file=sys.stderr)
        return 2
    try:
        payload = build_nodes_reconcile_payload(args)
    except (FileNotFoundError, OSError, ValueError, SchemaProviderError) as exc:
        payload = {"schema_version": _RECONCILE_SCHEMA_VERSION, "status": "blocked", "diagnostics": [_reconcile_diagnostic("runtime", "reconcile_error", f"reconciliation could not be completed: {type(exc).__name__}", target="reconcile", details={"error": str(exc)})], "remediations": []}
    print(json.dumps(_reconcile_jsonable(payload), indent=2, sort_keys=True))
    return 0 if payload["status"] == "ok" else 1


def _print_install_plan(payload: dict[str, object], *, json_output: bool) -> int:
    packs = payload["packs"]
    unresolved = payload["unresolved_class_types"]
    missing_classes = payload["missing_class_types"]
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if unresolved else 0
    if not missing_classes:
        print("No missing custom node classes detected from local node_index.json.")
        return 0
    if packs:
        print("Suggested custom node packs:")
        for pack in packs:
            classes = ", ".join(pack["classes"])
            packages = f" (pip: {', '.join(pack['pip_packages'])})" if pack["pip_packages"] else ""
            print(f"- {pack['name']}: {pack['repo']}{packages}")
            print(f"  classes: {classes}")
    if unresolved:
        print("Unmapped node classes:")
        for class_type in unresolved:
            print(f"- {class_type}")
        return 1
    return 0


def _cmd_nodes_install(args: argparse.Namespace) -> int:
    try:
        result = node_packs_install.install_pack(name=args.name, repo=args.repo, force=args.force)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
    print(f"{result.name}: {result.status}{detail}")
    if result.error:
        print(result.error, file=sys.stderr)
    return 0 if result.status in {"installed", "refreshed"} else 1


def _cmd_nodes_lookup(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_pack(args.query)
    except PackResolverError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = {
        "query": resolution.query,
        "query_type": resolution.query_type,
        "pack": resolution.ref.to_dict(),
        "candidates": [candidate.to_dict() for candidate in resolution.candidates],
        "cache_hit": resolution.cache_hit,
        "endpoint": resolution.endpoint,
    }
    return emit(payload, json=args.json, text_renderer=lambda data: data["pack"]["slug"])


def _cmd_nodes_refresh_template(args: argparse.Namespace) -> int:
    path = Path(args.file)
    original = path.read_text(encoding="utf-8")
    workflow = load_workflow_reference(str(path), allow_scratchpad=True)
    classes = {str(node.class_type) for node in workflow.nodes.values()}
    refs = []
    for entry in read_lockfile():
        class_set = set(getattr(entry, "class_set", ()) or ())
        if classes & class_set:
            refs.append(entry)
    slugs = sorted({getattr(entry, "slug", None) or entry.name for entry in refs})
    replacement = original
    if "custom_node_refs=" not in replacement:
        marker = "    output_prefix="
        insert = f"    custom_node_refs={slugs!r},\n"
        lines = replacement.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.startswith(marker):
                lines.insert(index + 1, insert)
                replacement = "".join(lines)
                break
    diff = "".join(difflib.unified_diff(original.splitlines(True), replacement.splitlines(True), fromfile=str(path), tofile=str(path)))
    status = "dry-run" if args.dry_run else "updated"
    if not args.dry_run:
        path.write_text(replacement, encoding="utf-8")
    payload = {"status": status, "custom_nodes": slugs, "diff": diff if args.diff else ""}
    return emit(payload, json=args.json, text_renderer=lambda data: data["status"])


def _cmd_nodes_ensure(args: argparse.Namespace) -> int:
    path = args.template or args.workflow
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(path, schema_provider=schema_provider, allow_scratchpad=True)
    try:
        missing_classes = node_packs_install.missing_class_types_for_workflow(workflow)
        packs, unresolved = node_packs_install.missing_packs_for_workflow(workflow)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.dry_run:
        payload = build_nodes_install_plan_payload(path, missing_classes, packs, unresolved)
        return _print_install_plan(payload, json_output=False)
    if not missing_classes:
        print("No missing custom node classes detected from local node_index.json.")
        return 0
    if unresolved:
        print("Unmapped node classes:")
        for class_type in unresolved:
            print(f"- {class_type}")
        return 1
    batch = node_packs_install.install_required_packs(packs)
    for result in batch.results:
        detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
        print(f"{result.name}: {result.status}{detail}")
        if result.error:
            print(result.error, file=sys.stderr)
    if not batch.ok:
        if batch.preflight.error:
            print(batch.preflight.error, file=sys.stderr)
        return 1
    print(
        "Nodepacks installed/refreshed. If a vibecomfy session is active, "
        "call session.reload_for_nodepack_change(...) or restart it."
    )
    return 0


def _cmd_nodes_lock(args: argparse.Namespace) -> int:
    lockfile_path = Path(getattr(args, "path", "custom_nodes.lock"))
    entries = read_lockfile(lockfile_path)
    locked: list[LockEntry] = []
    for entry in entries:
        pack_dir = _installed_nodepack_dir(entry.name)
        git_commit_sha = entry.git_commit_sha
        if entry.semantic_label and pack_dir is not None:
            git_commit_sha = _git_head(pack_dir) or git_commit_sha
        source_sha256 = dict(entry.source_sha256)
        if getattr(args, "with_source_sha256", False) and pack_dir is not None:
            source_sha256 = _source_sha256(pack_dir)
        locked.append(
            LockEntry(
                name=entry.name,
                git_commit_sha=git_commit_sha,
                url=entry.url,
                semantic_label=entry.semantic_label,
                source_sha256=source_sha256,
            )
        )
    write_lockfile(locked, lockfile_path)
    print(f"Wrote {lockfile_path} ({len(locked)} nodepacks)")
    return 0


def _cmd_nodes_restore(args: argparse.Namespace) -> int:
    entries = read_lockfile(Path(args.lockfile))
    ok = True
    for entry in entries:
        result = node_packs_install.restore_pack(entry)
        detail = f" {result.git_commit_sha}" if result.git_commit_sha else ""
        print(f"{result.name}: {result.status}{detail}")
        if result.error:
            print(result.error, file=sys.stderr)
        ok = ok and result.status in {"installed", "refreshed"}
    return 0 if ok else 1


def _installed_nodepack_dir(name: str) -> Path | None:
    candidate = node_packs_install.DEFAULT_INSTALL_ROOT / name
    return candidate if candidate.is_dir() else None


def _git_head(pack_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _source_sha256(pack_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for source in sorted(pack_dir.rglob("*.py")):
        if ".git" in source.parts:
            continue
        rel = source.relative_to(pack_dir).as_posix()
        hashes[rel] = hashlib.sha256(source.read_bytes()).hexdigest()
    return hashes


def _cmd_nodes_coverage(args: argparse.Namespace) -> int:
    """Schema completeness report for a workflow's class types."""
    schema_provider = get_schema_provider("auto")
    try:
        loaded = load_port_source(args.workflow, schema_provider=schema_provider)
    except Exception as exc:
        print(f"Failed to load workflow: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    lock_path = Path(args.lockfile) if getattr(args, "lockfile", None) else Path("custom_nodes.lock")
    coverage = build_workflow_coverage(
        loaded.workflow,
        schema_provider=schema_provider,
        lock_path=lock_path,
    )
    if args.json:
        print(json.dumps(coverage.to_json(), indent=2, sort_keys=True))
    else:
        print(_format_coverage(coverage))
    return 0


def _format_coverage(coverage) -> str:
    lines = []
    for entry in coverage.per_class:
        icon = {"typed_wrapper": "✅ typed wrapper", "raw_call": "⚡ raw_call", "missing_lock": "❌ missing_lock"}.get(
            entry["coverage"], f"? {entry['coverage']}"
        )
        lines.append(f"{entry['class_type']:40s} {entry['pack']:30s} {icon}")
    lines.append("")
    lines.append(f"Coverage: {coverage.typed_wrapper}/{coverage.total} ({coverage.to_json()['coverage_pct']}%)")
    lines.append(f"Falls through to raw_call: {coverage.raw_call}")
    lines.append(f"Missing from custom_nodes.lock: {coverage.missing_lock}")
    return "\n".join(lines)


def _cmd_nodes_drift(args: argparse.Namespace) -> int:
    """Schema-drift detector for a custom-node pack."""
    pack_name: str = args.pack
    from_ref: str | None = getattr(args, "from_ref", None)
    to_ref: str | None = getattr(args, "to_ref", None)

    # Resolve pack dir
    pack_dir = node_packs_install.DEFAULT_INSTALL_ROOT / pack_name
    if not pack_dir.is_dir():
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "message": f"Pack directory not found: {pack_dir}. Install the pack first with `vibecomfy nodes install {pack_name}`.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Pack unavailable: {pack_name}")
            print(f"  Directory not found: {pack_dir}")
            print(f"  Install with: vibecomfy nodes install {pack_name}")
        return 0

    # Check git
    if not (pack_dir / ".git").is_dir():
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "message": f"Pack directory {pack_dir} is not a git repository.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Pack unavailable: {pack_name}")
            print(f"  {pack_dir} is not a git repository")
        return 0

    # Resolve refs
    if from_ref is None:
        from_ref = "HEAD~1"
    if to_ref is None:
        to_ref = "HEAD"

    # Get schema snapshots
    from_python = _extract_pack_python_api(pack_dir, from_ref)
    to_python = _extract_pack_python_api(pack_dir, to_ref)

    if from_python is None or to_python is None:
        payload = {
            "status": "unavailable",
            "pack": pack_name,
            "from_ref": from_ref,
            "to_ref": to_ref,
            "message": "Could not extract Python API from one or both refs.",
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Schema diff unavailable for {pack_name}: {from_ref}..{to_ref}")
        return 0

    # Diff classes
    from_classes = _parse_class_defs(from_python)
    to_classes = _parse_class_defs(to_python)

    added = set(to_classes) - set(from_classes)
    removed = set(from_classes) - set(to_classes)
    modified: list[dict[str, Any]] = []

    for cls_name in set(from_classes) & set(to_classes):
        if from_classes[cls_name] != to_classes[cls_name]:
            modified.append({
                "class": cls_name,
                "from_inputs": from_classes[cls_name],
                "to_inputs": to_classes[cls_name],
            })

    # Find affected templates
    affected_templates: list[str] = []
    affected_template_diagnostics: list[Diagnostic] = []
    all_modified_classes = {m["class"] for m in modified} | added | removed
    if all_modified_classes:
        try:
            snapshot = build_corpus_snapshot()
        except Exception as exc:  # noqa: BLE001 - report incomplete impact analysis
            affected_template_diagnostics.append(
                _affected_template_diagnostic(
                    "affected_template_snapshot_failed",
                    (
                        "Class diff completed, but affected-template analysis could not "
                        "build the ready-template corpus snapshot."
                    ),
                    path=None,
                    exception=exc,
                )
            )
        else:
            for tpl in snapshot.templates_list:
                tpl_path = Path(tpl["path"])
                if not tpl_path.is_file():
                    continue
                try:
                    source = tpl_path.read_text(encoding="utf-8")
                except Exception as exc:  # noqa: BLE001 - continue scanning, but surface partial analysis
                    affected_template_diagnostics.append(
                        _affected_template_diagnostic(
                            "affected_template_read_failed",
                            "Class diff completed, but an affected-template source file could not be read.",
                            path=tpl_path,
                            exception=exc,
                        )
                    )
                    continue
                for ct in all_modified_classes:
                    if f"'{ct}'" in source or f'"{ct}"' in source:
                        affected_templates.append(tpl["id"])
                        break

    partial = bool(affected_template_diagnostics)

    payload = {
        "status": "partial" if partial else "ok",
        "pack": pack_name,
        "from_ref": from_ref,
        "to_ref": to_ref,
        "added_classes": sorted(added),
        "removed_classes": sorted(removed),
        "modified_classes": modified,
        "affected_templates": sorted(set(affected_templates)),
    }
    if partial:
        payload["partial"] = True
        payload["diagnostics"] = diagnostics_to_json(affected_template_diagnostics)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Schema diff: {pack_name} {from_ref}..{to_ref}")
        print(f"Added classes: {sorted(added) if added else '(none)'}")
        print(f"Removed classes: {sorted(removed) if removed else '(none)'}")
        if modified:
            print("Modified classes:")
            for m in modified:
                print(f"  {m['class']}: inputs changed")
        else:
            print("Modified classes: (none)")
        if affected_templates:
            print(f"\nAffected templates (use modified classes):")
            for tid in sorted(set(affected_templates)):
                print(f"  {tid}")
        else:
            print("\nAffected templates: (none)")
        if partial:
            print("\nClass diff completed, but affected-template analysis did not complete.")
            print(diagnostics_to_text(affected_template_diagnostics))
    return 1 if partial else 0


def _affected_template_diagnostic(
    code: str,
    message: str,
    *,
    path: Path | None,
    exception: BaseException,
) -> Diagnostic:
    details: dict[str, Any] = {
        "exception_type": type(exception).__name__,
        "exception": str(exception),
    }
    if path is not None:
        details["path"] = str(path)
    return Diagnostic(
        code=code,
        message=message,
        severity="error",
        recoverable=True,
        details=details,
    )


def _extract_pack_python_api(pack_dir: Path, ref: str) -> str | None:
    """Extract combined Python source from all .py files at a git ref."""
    try:
        result = subprocess.run(
            ["git", "-C", str(pack_dir), "ls-tree", "-r", "--name-only", ref],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    py_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]
    if not py_files:
        return None

    combined: list[str] = []
    for py_file in py_files[:50]:  # limit to prevent huge output
        try:
            r = subprocess.run(
                ["git", "-C", str(pack_dir), "show", f"{ref}:{py_file}"],
                check=True,
                capture_output=True,
                text=True,
            )
            combined.append(r.stdout)
        except (OSError, subprocess.CalledProcessError):
            continue

    return "\n".join(combined) if combined else None


def _parse_class_defs(source: str) -> dict[str, dict[str, Any]]:
    """Parse INPUT_TYPES-like class definitions from Python source."""
    classes: dict[str, dict[str, Any]] = {}
    # Find class definitions and their INPUT_TYPES
    class_pattern = re.compile(r"class\s+(\w+)\s*[:\(]")
    inputs_pattern = re.compile(r"INPUT_TYPES\s*\(\s*\)\s*:\s*\n?\s*return\s*\{[^}]*\}")

    for cls_match in class_pattern.finditer(source):
        cls_name = cls_match.group(1)
        # Try to find INPUT_TYPES after the class
        rest = source[cls_match.end():]
        next_class = class_pattern.search(rest)
        section = rest[:next_class.start()] if next_class else rest

        # Extract required inputs
        required = re.findall(r'"required"\s*:\s*\{([^}]*)\}', section, re.DOTALL)
        if required:
            classes[cls_name] = {"has_required_inputs": True}
        else:
            classes[cls_name] = {"has_required_inputs": False}

    return classes


DEFAULT_WRAPPER_OUT_DIR = Path("vibecomfy/nodes")
DEFAULT_LOCKFILE = Path("custom_nodes.lock")


def _resolve_sources(source_arg: str) -> tuple[str, ...]:
    """Map the CLI ``--source`` flag to a discovery precedence tuple."""
    if source_arg == "auto":
        return _wrapper_discovery.DEFAULT_PRECEDENCE
    return (source_arg,)


def _cmd_nodes_generate_wrappers(args: argparse.Namespace) -> int:
    if args.all and args.pack_slug:
        print("--all and an explicit pack slug are mutually exclusive", file=sys.stderr)
        return 2
    if not args.all and not args.pack_slug:
        print("Provide a pack slug or --all", file=sys.stderr)
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = _resolve_sources(args.source)
    server_url = args.server_url

    if args.all:
        slugs = _wrapper_discovery._read_lockfile_pack_slugs(DEFAULT_LOCKFILE)  # noqa: SLF001 — explicit helper
    else:
        slugs = [args.pack_slug]

    results: list[dict] = []
    failed_packs: list[str] = []
    for slug in slugs:
        try:
            specs = _wrapper_discovery.discover_pack(slug, sources=sources, server_url=server_url)
        except (OSError, ValueError) as exc:
            results.append({"pack": slug, "status": "error", "error": str(exc)})
            failed_packs.append(slug)
            continue
        if not specs:
            results.append({"pack": slug, "status": "no_discovery", "class_count": 0})
            failed_packs.append(slug)
            continue
        timestamp = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc) if args.deterministic_timestamp else _dt.datetime.now(_dt.timezone.utc)
        render = _wrapper_codegen.render_pack(slug, specs, out_dir=out_dir, timestamp=timestamp)
        prior = render.module_path.read_text(encoding="utf-8") if render.module_path.exists() else None
        action = "no_change"
        if prior != render.source_text:
            action = "create" if prior is None else "update"
        diff_text = ""
        if args.diff and prior is not None and prior != render.source_text:
            diff_text = "".join(
                difflib.unified_diff(
                    prior.splitlines(keepends=True),
                    render.source_text.splitlines(keepends=True),
                    fromfile=str(render.module_path),
                    tofile=str(render.module_path) + " (proposed)",
                )
            )
        if not args.dry_run and action != "no_change":
            render.module_path.write_text(render.source_text, encoding="utf-8")
        results.append(
            {
                "pack": slug,
                "status": "ok",
                "action": action,
                "module_path": str(render.module_path),
                "class_count": render.class_count,
                "skipped_classes": list(render.skipped_classes),
                "source_sha256": render.source_sha256,
                "diff": diff_text,
            }
        )

    if args.json:
        print(json.dumps({"results": results}, indent=2, sort_keys=True))
    else:
        for entry in results:
            if entry["status"] == "ok":
                print(
                    f"{entry['pack']}: {entry['action']} {entry['module_path']} "
                    f"(classes={entry['class_count']}, sha={entry['source_sha256'][:12]})"
                )
                if entry["diff"]:
                    print(entry["diff"])
            elif entry["status"] == "no_discovery":
                print(f"{entry['pack']}: no discovery source available; skipping", file=sys.stderr)
            else:
                print(f"{entry['pack']}: error: {entry.get('error')}", file=sys.stderr)
    return 1 if failed_packs else 0


def _cmd_nodes_wrapper_status(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    sources = _resolve_sources(args.source)
    slugs = _wrapper_discovery._read_lockfile_pack_slugs(Path(args.lockfile))  # noqa: SLF001
    rows: list[dict] = []
    for slug in slugs:
        module_name = _wrapper_codegen._slug_to_module_name(slug)  # noqa: SLF001
        module_path = out_dir / f"{module_name}.py"
        existing_header = None
        if module_path.exists():
            existing_header = _wrapper_codegen.parse_generated_header(
                module_path.read_text(encoding="utf-8")
            )
        # Compute the *current* source sha for what a regen would produce.
        current_sha = None
        class_count = None
        try:
            specs = _wrapper_discovery.discover_pack(slug, sources=sources)
        except (OSError, ValueError):
            specs = []
        if specs:
            render = _wrapper_codegen.render_pack(slug, specs, out_dir=out_dir)
            current_sha = render.source_sha256
            class_count = render.class_count
        existing_sha = existing_header.get("source_sha256") if existing_header else None
        if not module_path.exists():
            state = "missing"
        elif existing_header is None:
            state = "hand_written"
        elif current_sha is None:
            state = "drift_unknown"
        elif current_sha == existing_sha:
            state = "current"
        else:
            state = "drifted"
        rows.append(
            {
                "pack": slug,
                "state": state,
                "module_path": str(module_path),
                "existing_source_sha256": existing_sha,
                "current_source_sha256": current_sha,
                "class_count": class_count,
            }
        )
    if args.json:
        print(json.dumps({"packs": rows}, indent=2, sort_keys=True))
    else:
        for row in rows:
            extra = ""
            if row["class_count"] is not None:
                extra = f" classes={row['class_count']}"
            print(f"{row['pack']:40s} {row['state']:14s} {row['module_path']}{extra}")
    return 0


def _cmd_nodes_generate_widget_schema(args: argparse.Namespace) -> int:
    sources = _resolve_sources(args.source)
    try:
        specs = _wrapper_discovery.discover_pack(args.pack_slug, sources=sources, server_url=args.server_url)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not specs:
        print(f"No discovery source produced specs for {args.pack_slug!r}", file=sys.stderr)
        return 1
    text = _wrapper_codegen.render_widget_schema(specs)
    if args.json:
        print(json.dumps({"pack": args.pack_slug, "widget_schema": text}, indent=2))
    else:
        print(f"# WIDGET_SCHEMA entries for pack: {args.pack_slug}")
        print(text)
    return 0


def register(subparsers) -> None:
    nodes = subparsers.add_parser("nodes")
    nodes_sub = nodes.add_subparsers(dest="subcmd", required=True)
    nodes_list = nodes_sub.add_parser("list")
    nodes_list.add_argument("--limit", type=int, default=200)
    nodes_list.add_argument("--json", action="store_true")
    nodes_list.set_defaults(func=_cmd_nodes_list)
    nodes_spec = nodes_sub.add_parser("spec")
    nodes_spec.add_argument("class_type")
    nodes_spec.add_argument(
        "--object-info-cache",
        help="Use a captured ComfyUI /object_info JSON file, for example one fetched from a RunPod runtime.",
    )
    nodes_spec.set_defaults(func=_cmd_nodes_spec)
    nodes_compatible = nodes_sub.add_parser("compatible-with", help="Find or check schema socket compatibility.")
    nodes_compatible.add_argument("type_or_from_class")
    nodes_compatible.add_argument("to_class", nargs="?")
    nodes_compatible.add_argument("to_input", nargs="?")
    nodes_compatible.add_argument("--as", dest="socket_role", choices=("input", "output"), default="output")
    nodes_compatible.add_argument("--from-output", default="0")
    nodes_compatible.add_argument("--object-info-cache")
    nodes_compatible.add_argument("--json", action="store_true")
    nodes_compatible.set_defaults(func=_cmd_nodes_compatible_with)
    nodes_install = nodes_sub.add_parser("install-plan")
    nodes_install.add_argument("path")
    nodes_install.add_argument("--json", action="store_true")
    nodes_install.set_defaults(func=_cmd_nodes_install_plan)
    nodes_reconcile = nodes_sub.add_parser(
        "reconcile", help="Report deterministic local node/model/runtime reconciliation state."
    )
    nodes_reconcile.add_argument("--workflow", required=True)
    nodes_reconcile.add_argument("--json", action="store_true", required=True)
    nodes_reconcile.add_argument("--lockfile", default=None)
    nodes_reconcile.add_argument("--registry", default=None)
    nodes_reconcile.add_argument("--models-root", default=None)
    nodes_reconcile.add_argument("--server-url", default=None)
    nodes_reconcile.set_defaults(func=_cmd_nodes_reconcile)
    nodes_install_pack = nodes_sub.add_parser("install")
    nodes_install_pack.add_argument("name", nargs="?")
    nodes_install_pack.add_argument("--repo")
    nodes_install_pack.add_argument("--force", action="store_true", default=False)
    nodes_install_pack.set_defaults(func=_cmd_nodes_install)
    nodes_lookup = nodes_sub.add_parser("lookup")
    nodes_lookup.add_argument("query")
    nodes_lookup.add_argument("--json", action="store_true")
    nodes_lookup.set_defaults(func=_cmd_nodes_lookup)
    nodes_refresh = nodes_sub.add_parser("refresh-template")
    nodes_refresh.add_argument("file")
    nodes_refresh.add_argument("--dry-run", action="store_true")
    nodes_refresh.add_argument("--diff", action="store_true")
    nodes_refresh.add_argument("--json", action="store_true")
    nodes_refresh.set_defaults(func=_cmd_nodes_refresh_template)
    nodes_ensure = nodes_sub.add_parser("ensure")
    ensure_source = nodes_ensure.add_mutually_exclusive_group(required=True)
    ensure_source.add_argument("--template")
    ensure_source.add_argument("--workflow")
    nodes_ensure.add_argument("--dry-run", action="store_true")
    nodes_ensure.set_defaults(func=_cmd_nodes_ensure)
    nodes_lock = nodes_sub.add_parser("lock")
    nodes_lock.add_argument("--path", default="custom_nodes.lock")
    nodes_lock.add_argument("--with-source-sha256", action="store_true", default=False)
    nodes_lock.set_defaults(func=_cmd_nodes_lock)
    nodes_restore = nodes_sub.add_parser("restore")
    nodes_restore.add_argument("--lockfile", default="custom_nodes.lock")
    nodes_restore.set_defaults(func=_cmd_nodes_restore)

    nodes_coverage = nodes_sub.add_parser("coverage", help="Schema completeness report for a workflow's class types.")
    nodes_coverage.add_argument("workflow")
    nodes_coverage.add_argument("--json", action="store_true")
    nodes_coverage.add_argument("--lockfile", default="custom_nodes.lock", help="Path to custom_nodes.lock")
    nodes_coverage.set_defaults(func=_cmd_nodes_coverage)

    nodes_drift = nodes_sub.add_parser("drift", help="Schema-drift detector for a custom-node pack.")
    nodes_drift.add_argument("pack", help="Custom node pack name (e.g. ComfyUI-KJNodes)")
    nodes_drift.add_argument("--from", dest="from_ref", help="Source git ref (default: HEAD~1)")
    nodes_drift.add_argument("--to", dest="to_ref", help="Target git ref (default: HEAD)")
    nodes_drift.add_argument("--json", action="store_true")
    nodes_drift.set_defaults(func=_cmd_nodes_drift)

    nodes_generate = nodes_sub.add_parser(
        "generate-wrappers",
        help="Generate typed wrappers for one or all custom-node packs.",
    )
    nodes_generate.add_argument("pack_slug", nargs="?")
    nodes_generate.add_argument("--all", action="store_true", default=False)
    nodes_generate.add_argument(
        "--source",
        choices=["live", "cache", "snapshot", "source", "auto"],
        default="auto",
    )
    nodes_generate.add_argument("--server-url", default=None)
    nodes_generate.add_argument("--out", default=str(DEFAULT_WRAPPER_OUT_DIR))
    nodes_generate.add_argument("--dry-run", action="store_true", default=False)
    nodes_generate.add_argument("--diff", action="store_true", default=False)
    nodes_generate.add_argument("--json", action="store_true", default=False)
    nodes_generate.add_argument(
        "--deterministic-timestamp",
        action="store_true",
        default=True,
        help="Use 1970-01-01 timestamp for byte-identical determinism (default: on).",
    )
    nodes_generate.set_defaults(func=_cmd_nodes_generate_wrappers)

    nodes_status = nodes_sub.add_parser(
        "wrapper-status",
        help="Report which packs have wrappers and whether they are drifted.",
    )
    nodes_status.add_argument("--lockfile", default=str(DEFAULT_LOCKFILE))
    nodes_status.add_argument("--out", default=str(DEFAULT_WRAPPER_OUT_DIR))
    nodes_status.add_argument(
        "--source",
        choices=["live", "cache", "snapshot", "source", "auto"],
        default="auto",
    )
    nodes_status.add_argument("--json", action="store_true", default=False)
    nodes_status.set_defaults(func=_cmd_nodes_wrapper_status)

    nodes_widget_schema = nodes_sub.add_parser(
        "generate-widget-schema",
        help="Emit WIDGET_SCHEMA entries for a pack (auxiliary; auxiliary to Sweep 2).",
    )
    nodes_widget_schema.add_argument("pack_slug")
    nodes_widget_schema.add_argument(
        "--source",
        choices=["live", "cache", "snapshot", "source", "auto"],
        default="auto",
    )
    nodes_widget_schema.add_argument("--server-url", default=None)
    nodes_widget_schema.add_argument("--json", action="store_true", default=False)
    nodes_widget_schema.set_defaults(func=_cmd_nodes_generate_widget_schema)
